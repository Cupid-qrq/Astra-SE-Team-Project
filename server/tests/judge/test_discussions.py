import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from app.modules.community.discussions import Discussions
from app.modules.identity.domain import Fault
from app.shared.effects import TransactionalEffects
from app.shared.metadata import metadata
from app.shared.repository import SqlRepository


@pytest.fixture
def world():
    url = os.environ.get("ASTRA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL test URL required")
    engine = create_engine(url)
    with engine.connect() as c:
        transaction = c.begin()
        schema = "discussion_" + uuid4().hex
        c.exec_driver_sql(f"CREATE SCHEMA {schema}")
        c.exec_driver_sql(f"SET LOCAL search_path TO {schema}")
        metadata.create_all(c)
        repo = SqlRepository(c)
        repo.add("policy_guard", dict(guard_id=1, revision=1))
        now = repo.now()

        def user(role):
            return repo.add(
                "users",
                dict(
                    user_id=str(uuid4()),
                    login_name="u" + uuid4().hex[:20],
                    display_name=role,
                    role=role,
                    status="ACTIVE",
                    password_hash="hash",
                    must_change_password=False,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                ),
            )

        teacher, student, other = user("TEACHER"), user("STUDENT"), user("STUDENT")
        cid, pid, vid, family = (str(uuid4()) for _ in range(4))
        repo.add(
            "courses",
            dict(
                course_id=cid,
                teacher_id=teacher["user_id"],
                title="course",
                status="ACTIVE",
                revision=1,
                archived_at=None,
                created_at=now,
                updated_at=now,
            ),
        )
        for u in (student, other):
            repo.add(
                "course_members",
                dict(course_id=cid, user_id=u["user_id"], status="ACTIVE", joined_at=now),
            )
        repo.add(
            "problem_families",
            dict(canonical_problem_id=family, owner_teacher_id=teacher["user_id"], label="family"),
        )
        repo.add(
            "problems",
            dict(
                problem_id=pid,
                canonical_problem_id=family,
                owner_course_id=cid,
                practice_released=False,
                practice_version_id=None,
                revision=1,
                created_at=now,
                updated_at=now,
            ),
        )
        repo.add(
            "problem_versions",
            dict(
                version_id=vid,
                problem_id=pid,
                version_no=1,
                title="problem",
                statement="statement",
                samples=[{}],
                tags=[],
                profile={},
                source_ref="",
                checksum="a" * 64,
                published_at=now,
                revision=1,
                published_preflight_id=None,
                created_at=now,
                updated_at=now,
            ),
        )
        repo.change("problems", pid, practice_released=True, practice_version_id=vid)
        service = Discussions(repo, TransactionalEffects(repo, str(uuid4())))
        yield repo, service, teacher, student, other, cid, pid, vid
        transaction.rollback()
    engine.dispose()


def create(w, actor=None):
    _, service, _, student, _, cid, pid, vid = w
    return service.create(
        actor or student,
        cid,
        pid,
        dict(version_id=vid, title="Question", body='<img src="https://outside.invalid/a">'),
    )


def test_hide_projection_roles_and_revision(world):
    repo, service, teacher, student, other, *_ = world
    thread = create(world)
    assert thread["is_mine"] and thread["revision"] == 1
    hidden = service.update(
        student,
        thread["thread_id"],
        dict(expected_revision=1, hidden=True, reason="hide my own discussion"),
    )
    assert hidden["body"] == "" and hidden["title"] == "已隐藏的讨论"
    assert service.read(other, thread["thread_id"])["thread"]["body"] == ""
    assert service.read(teacher, thread["thread_id"])["thread"]["body"].startswith("<img")
    assert repo.get("discussion_threads", thread["thread_id"])["body"].startswith("<img")
    with pytest.raises(Fault) as error:
        service.update(
            student,
            thread["thread_id"],
            dict(expected_revision=1, resolved=True, reason="resolve discussion now"),
        )
    assert error.value.code == "REVISION_CONFLICT"


def test_membership_course_and_version_isolation(world):
    repo, service, teacher, student, other, cid, pid, vid = world
    thread = create(world)
    repo.change("course_members", (cid, other["user_id"]), status="DISABLED")
    with pytest.raises(Fault):
        service.read(other, thread["thread_id"])
    with pytest.raises(Fault):
        service.list(student, str(uuid4()), pid, vid)
    with pytest.raises(Fault):
        service.list(student, cid, pid, str(uuid4()))
    repo.change("users", student["user_id"], status="DISABLED")
    with pytest.raises(Fault):
        service.read(student, thread["thread_id"])


def test_lock_moderation_and_archive(world):
    repo, service, teacher, student, other, cid, *_ = world
    thread = create(world)
    with pytest.raises(Fault):
        service.update(
            student,
            thread["thread_id"],
            dict(expected_revision=1, locked=True, reason="lock this discussion now"),
        )
    service.update(
        teacher,
        thread["thread_id"],
        dict(expected_revision=1, locked=True, pinned=True, reason="lock this discussion now"),
    )
    with pytest.raises(Fault):
        service.reply(other, thread["thread_id"], dict(body="reply"))
    repo.change("courses", cid, status="ARCHIVED", archived_at=repo.now())
    assert service.read(student, thread["thread_id"])["thread"]["locked"]
    with pytest.raises(Fault):
        service.update(
            teacher,
            thread["thread_id"],
            dict(expected_revision=2, locked=False, reason="unlock discussion now"),
        )
    with pytest.raises(Fault):
        create(world, teacher)


def test_rate_and_reply_hide(world):
    repo, service, teacher, student, other, *_ = world
    thread = create(world)
    with pytest.raises(Fault) as error:
        service.reply(student, thread["thread_id"], dict(body="reply"))
    assert error.value.status == 429
    reply = service.reply(other, thread["thread_id"], dict(body="reply"))
    hidden = service.update_reply(
        other,
        reply["reply_id"],
        dict(expected_revision=1, hidden=True, reason="hide this own reply now"),
    )
    assert hidden["body"] == ""
    assert service.read(student, thread["thread_id"])["thread"]["reply_count"] == 1
    assert service.read(teacher, thread["thread_id"])["replies"][0]["body"] == "reply"
    repo.change(
        "discussion_threads", thread["thread_id"], created_at=repo.now() - timedelta(seconds=11)
    )
    assert service.reply(student, thread["thread_id"], dict(body="allowed now"))["is_mine"]


@pytest.mark.parametrize(
    "body",
    [
        dict(title=" ", body="x"),
        dict(title="x", body=" "),
        dict(title="x", body="x", author_id="forged"),
        dict(title="x", body="\0"),
    ],
)
def test_invalid_content(world, body):
    _, service, _, student, _, cid, pid, vid = world
    with pytest.raises(Fault):
        service.create(student, cid, pid, dict(version_id=vid, **body))


def test_hidden_thread_hides_replies_and_author_cannot_restore(world):
    _, service, teacher, student, other, *_ = world
    thread = create(world)
    reply = service.reply(other, thread["thread_id"], dict(body="secret conversation"))
    service.update(
        teacher,
        thread["thread_id"],
        dict(expected_revision=1, hidden=True, reason="hide discussion for moderation"),
    )
    public = service.read(student, thread["thread_id"])
    assert public["replies"] == [] and public["thread"]["reply_count"] == 0
    assert len(service.read(teacher, thread["thread_id"])["replies"]) == 1
    with pytest.raises(Fault):
        service.update(
            student,
            thread["thread_id"],
            dict(expected_revision=2, hidden=False, reason="restore discussion by author"),
        )
    service.update_reply(
        teacher,
        reply["reply_id"],
        dict(expected_revision=1, hidden=True, reason="hide reply for moderation"),
    )
    with pytest.raises(Fault):
        service.update_reply(
            other,
            reply["reply_id"],
            dict(expected_revision=2, hidden=False, reason="restore reply by author"),
        )


def test_scheduled_assignment_cannot_open_discussion_or_practice(world):
    repo, service, teacher, student, _, cid, pid, vid = world
    now = repo.now()
    aid = str(uuid4())
    repo.add(
        "assignments",
        dict(
            assignment_id=aid,
            course_id=cid,
            title="scheduled",
            open_at=now + timedelta(hours=1),
            due_at=now + timedelta(hours=2),
            ai_policy="DISABLED",
            published_at=now,
            revision=1,
            grade_epoch=1,
            fairness_review="NONE",
            active_grade_version=None,
            active_rejudge_batch_id=None,
            created_at=now,
            updated_at=now,
        ),
    )
    repo.add(
        "assignment_items",
        dict(
            assignment_id=aid,
            problem_id=pid,
            original_version_id=vid,
            effective_version_id=vid,
            points=100,
        ),
    )
    # Even explicitly released practice is embargoed by the scheduled active family.
    with pytest.raises(Fault):
        service.list(student, cid, pid, vid)
    with pytest.raises(Fault):
        create(world)
    assert service.list(teacher, cid, pid, vid) == []
    repo.change("assignments", aid, open_at=now - timedelta(seconds=1))
    assert create(world)["version_id"] == vid


def test_matching_membership_does_not_allow_foreign_course_problem(world):
    repo, service, teacher, student, _, cid, pid, vid = world
    foreign = str(uuid4())
    now = repo.now()
    repo.add(
        "courses",
        dict(
            course_id=foreign,
            teacher_id=teacher["user_id"],
            title="other course",
            status="ACTIVE",
            revision=1,
            archived_at=None,
            created_at=now,
            updated_at=now,
        ),
    )
    repo.add(
        "course_members",
        dict(course_id=foreign, user_id=student["user_id"], status="ACTIVE", joined_at=now),
    )
    for actor in (teacher, student):
        with pytest.raises(Fault):
            service.list(actor, foreign, pid, vid)
        with pytest.raises(Fault):
            service.create(actor, foreign, pid, dict(version_id=vid, title="x", body="x"))


def test_hourly_limit_combines_threads_and_replies(world):
    repo, service, _, student, _, cid, *_ = world
    first = create(world)
    original = repo.get("discussion_threads", first["thread_id"])
    now = repo.now()
    repo.change("discussion_threads", first["thread_id"], created_at=now - timedelta(minutes=1))
    for i in range(29):
        repo.add(
            "discussion_replies",
            dict(
                reply_id=str(uuid4()),
                thread_id=first["thread_id"],
                author_id=student["user_id"],
                body="historical reply",
                hidden=False,
                revision=1,
                created_at=now - timedelta(seconds=60 + i * 11),
            ),
        )
    with pytest.raises(Fault) as error:
        create(world)
    assert error.value.code == "DISCUSSION_HOURLY_LIMIT"
    assert len(repo.rows("discussion_threads", course_id=cid)) == 1
    events = repo.rows("audit_events", object_id=original["thread_id"])
    assert events[0]["actor_id"] == student["user_id"]
    assert events[0]["action"] == "DISCUSSION_CREATED"
