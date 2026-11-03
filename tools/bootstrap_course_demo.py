# ruff: noqa: E402
"""Create an empty *_demo database's public course demo using real services/execution."""

import hashlib
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.adapters.course_executor import CourseExecutor
from app.adapters.judge_profiles import SnapshotCatalog
from app.modules.assignments.application import Assignments
from app.modules.courses.application import Courses
from app.modules.grades.application import Grades
from app.modules.identity.domain import utc
from app.modules.judging.preflight import TransactionalPreflight
from app.modules.judging.worker import PreflightWorker
from app.modules.judging.worker_store import WorkerStore
from app.modules.learning.application import seed_global_feedback
from app.modules.operations.application import deliver
from app.modules.problems.application import Problems
from app.modules.submissions.application import Submissions
from app.modules.submissions.worker import SubmissionWorker
from app.modules.submissions.worker_store import SubmissionStore
from app.shared.effects import TransactionalEffects
from app.shared.passwords import ArgonPasswords
from app.shared.repository import SqlRepository


def main():
    url = make_url(os.environ["ASTRA_DATABASE_URL"])
    if not (url.database or "").endswith("_demo"):
        raise ValueError("Dedicated *_demo database required")
    password = os.environ["ASTRA_DEMO_PASSWORD"]
    if len(password) < 12:
        raise ValueError("Demo password too short")
    profile = json.loads(Path(os.environ["ASTRA_PROFILES_FILE"]).read_text(encoding="utf-8"))[0]
    image = profile["languages"][0]["image_digest"]
    catalog = SnapshotCatalog((profile,))
    executor = CourseExecutor(
        os.environ.get("ASTRA_EXECUTOR_HOST", "oldali"),
        image,
        state_dir="/var/lib/astra-course-executor-demo",
    )
    engine = create_engine(url, hide_parameters=True)
    cfg = Config(str(ROOT / "server/alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        repo = SqlRepository(conn)
        if repo.rows("users"):
            raise ValueError("Demo database is not empty")
        now = repo.now()
        ids = {}
        encoded = ArgonPasswords().hash(password)
        for role, name in [
            ("ADMIN", "admin_demo"),
            ("TEACHER", "teacher_demo"),
            ("STUDENT", "student_demo"),
        ]:
            uid = str(uuid4())
            ids[role] = uid
            repo.add(
                "users",
                dict(
                    user_id=uid,
                    login_name=name,
                    display_name={
                        "ADMIN": "演示管理员",
                        "TEACHER": "演示教师",
                        "STUDENT": "演示学生",
                    }[role],
                    role=role,
                    status="ACTIVE",
                    password_hash=encoded,
                    must_change_password=False,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                ),
            )
        effects = TransactionalEffects(repo, str(uuid4()))
        teacher = repo.required("users", ids["TEACHER"])
        cid = Courses(repo, effects).create(teacher, {"title": "Astra 三角色验收课程"})["course_id"]
        ids["course_id"] = cid
        course = repo.required("courses", cid)
        Courses(repo, effects).member(
            teacher,
            cid,
            ids["STUDENT"],
            dict(status="ACTIVE", expected_revision=course["revision"]),
        )
        seed_global_feedback(repo, ids["ADMIN"])
    WorkerStore(engine).bind_executor(
        hashlib.sha256(json.dumps(executor.command, separators=(",", ":")).encode()).hexdigest()
    )
    preflight = PreflightWorker(
        WorkerStore(engine), catalog, {"cpp17": executor, "python3": executor}
    )
    tasks = []
    for title, operation in [
        ("两数之和", "sum"),
        ("较大数", "max"),
        ("两数之和·修订为乘积", "product"),
    ]:
        expression = {"sum": "a+b", "max": "(a>b?a:b)", "product": "a*b"}[operation]
        py = {
            "sum": "print(sum(map(int,input().split())))",
            "max": "print(max(map(int,input().split())))",
            "product": "a,b=map(int,input().split());print(a*b)",
        }[operation]
        cpp = (
            "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<" + expression + ";}"
        )
        answer = {"sum": "5", "max": "3", "product": "6"}[operation]
        with engine.begin() as conn:
            repo = SqlRepository(conn)
            repo.guard()
            effects = TransactionalEffects(repo, str(uuid4()))
            teacher = repo.required("users", ids["TEACHER"])
            service = Problems(repo, effects)
            pid = (
                tasks[0]["problem_id"]
                if operation == "product"
                else service.create(teacher, {"course_id": cid})["problem_id"]
            )
            vid = service.create_version(
                teacher,
                dict(
                    problem_id=pid,
                    title=title,
                    statement="输入两个整数，输出" + title + "。",
                    samples=[dict(input="2 3", output=answer)],
                    tags=["基础"],
                    profile=profile,
                    source_ref="公开课程演示",
                ),
            )["version_id"]
            rev = service.put_case(
                teacher,
                vid,
                1,
                dict(input_text="2 3", answer_text=answer, expected_revision=1),
            )["revision"]
            for language, code in [("python3", py), ("cpp17", cpp)]:
                rev = service.put_reference(
                    teacher, vid, language, dict(code=code, expected_revision=rev)
                )["revision"]
            port = TransactionalPreflight(repo, catalog, effects)
            receipt = port.enqueue(repo, teacher, vid)
        if not preflight.run_once():
            raise RuntimeError("Demo preflight not claimed")
        with engine.begin() as conn:
            repo = SqlRepository(conn)
            effects = TransactionalEffects(repo, str(uuid4()))
            port = TransactionalPreflight(repo, catalog, effects)
            Problems(repo, effects, port).publish(
                repo.required("users", ids["TEACHER"]),
                vid,
                dict(
                    expected_revision=rev,
                    preflight_id=receipt["preflight_id"],
                    reason="公开两语言真实预检通过",
                ),
            )
        tasks.append(dict(problem_id=pid, version_id=vid, code=py))
        print("DEMO_VERSION_PUBLISHED " + operation, flush=True)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        teacher = repo.required("users", ids["TEACHER"])
        now = repo.now()
        for label, due in [
            ("开放作业", now + timedelta(hours=8)),
            ("成绩与重评验收", now + timedelta(seconds=45)),
        ]:
            service = Assignments(repo, effects)
            aid = service.create(
                teacher,
                dict(
                    course_id=cid,
                    title=label,
                    items=[
                        dict(
                            problem_id=t["problem_id"],
                            version_id=t["version_id"],
                            points=50,
                        )
                        for t in tasks[:2]
                    ],
                    open_at=utc(now - timedelta(minutes=1)),
                    due_at=utc(due),
                    ai_policy="DISABLED",
                ),
            )["assignment_id"]
            service.publish(teacher, aid, dict(expected_revision=1, reason="演示作业"))
            ids[label] = aid
    student_worker = SubmissionWorker(
        SubmissionStore(engine), catalog, {"cpp17": executor, "python3": executor}
    )
    for index, task in enumerate(tasks[:2]):
        if index:
            time.sleep(5.1)
        with engine.begin() as conn:
            repo = SqlRepository(conn)
            effects = TransactionalEffects(repo, str(uuid4()))
            Submissions(repo, effects).accept(
                repo.required("users", ids["STUDENT"]),
                dict(
                    assignment_id=ids["成绩与重评验收"],
                    problem_id=task["problem_id"],
                    language_key="python3",
                    code=task["code"],
                ),
                str(uuid4()),
                "FORMAL",
                str(uuid4()),
            )
        student_worker.run_once()
    while True:
        with engine.connect() as conn:
            due = conn.scalar(
                text("SELECT due_at FROM assignments WHERE assignment_id=:id"),
                {"id": ids["成绩与重评验收"]},
            )
            now = conn.scalar(text("SELECT clock_timestamp()"))
        if now >= due:
            break
        time.sleep(1)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        Grades(repo, effects).publish(
            repo.required("users", ids["TEACHER"]),
            ids["成绩与重评验收"],
            dict(expected_revision=2, reason="真实评测完成的演示成绩"),
        )
        deliver(repo)
    Path(os.environ["ASTRA_DEMO_MANIFEST"]).write_text(
        json.dumps(dict(ids=ids, versions=tasks), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    engine.dispose()
    print("DEMO_READY", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit("DEMO_BOOTSTRAP_FAILED_CHECK_CONFIGURATION") from None
