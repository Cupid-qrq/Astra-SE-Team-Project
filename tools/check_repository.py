"""检查规划结构、需求追踪、相对链接和只读归档；不运行系统验收。"""

import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote
import zipfile

from check_runtime import requires_runtime, runtime_files, source_files

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    checks = 0

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(message)

    required = [
        "README.md", "AGENTS.md", "CONTRIBUTING.md", "docs/00-development-plan.md",
        "docs/01-requirements.md", "docs/02-architecture.md", "docs/03-api-contract.md",
        "docs/04-data-design.md", "docs/05-ui-specification.md", "docs/06-roadmap.md",
        "docs/07-quality-and-acceptance.md", "docs/08-deployment-and-operations.md",
        "docs/project-status.md", "specs/traceability.json",
        ".github/workflows/repository.yml", ".github/pull_request_template.md",
        "apps/web/README.md", "server/README.md", "tests/README.md", "infra/README.md"
    ]
    for name in required:
        check((ROOT / name).is_file(), f"缺少 {name}")

    files = [ROOT / n for n in ("README.md", "AGENTS.md", "CONTRIBUTING.md")]
    for folder in ("docs", "apps", "server", "tests", "infra", "specs", ".github"):
        files.extend(path for path in source_files(ROOT / folder) if path.suffix == '.md')
    files.append(ROOT / "archive/README.md")
    for file in files:
        if not file.is_file():
            continue
        content = file.read_text(encoding="utf-8")
        check(not content.startswith("\ufeff"), f"UTF-8 BOM: {file.relative_to(ROOT)}")
        check(content.endswith("\n"), f"缺少末尾换行: {file.relative_to(ROOT)}")
        check(len(re.findall(r"^```", content, re.M)) % 2 == 0,
              f"代码围栏未配对: {file.relative_to(ROOT)}")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            if re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
                continue
            target = unquote(target.split("#", 1)[0].strip("<>"))
            if not target:
                continue
            path = (file.parent / target).resolve()
            check(path.is_relative_to(ROOT), f"链接越出仓库: {file.name}: {target}")
            check(path.exists(), f"断链: {file.relative_to(ROOT)} -> {target}")

    req = (ROOT / "docs/01-requirements.md").read_text(encoding="utf-8")
    trace = json.loads((ROOT / "specs/traceability.json").read_text(encoding="utf-8"))
    roadmap = (ROOT / "docs/06-roadmap.md").read_text(encoding="utf-8")
    api = (ROOT / "docs/03-api-contract.md").read_text(encoding="utf-8")
    data = (ROOT / "docs/04-data-design.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/02-architecture.md").read_text(encoding="utf-8")
    tasks = {task["id"]: task for task in trace.get("tasks", [])}
    documented_tasks = {i: (o, int(d)) for i, o, d in re.findall(
        r"^\| (P[0-3]-[AB]\d+) \| ([AB]) \| (\d+) \|", roadmap, re.M)}
    check(trace.get("schema_version") == 2, "追踪清单版本应为2")
    check(len(tasks) == len(trace.get("tasks", [])) and bool(tasks), "任务为空或重复")
    check(set(tasks) == set(documented_tasks), "路线文档与任务清单不一致")
    for key, task in tasks.items():
        check(documented_tasks.get(key) == (task["owner"], task["person_days"]),
              f"{key}负责人或工作量与路线不符")
        check(task["phase"] == key[:2] and task["owner"] == key[3], f"{key}阶段/负责人错误")
        for dep in task["depends_on"]:
            check(dep in tasks, f"{key}依赖不存在: {dep}")
            if dep in tasks:
                check(tasks[dep]["phase"] <= task["phase"], f"{key}依赖后续阶段")
    pending = {key: set(task["depends_on"]) for key, task in tasks.items()}
    while pending:
        ready = {key for key, deps in pending.items() if not deps}
        if not ready:
            break
        pending = {key: deps - ready for key, deps in pending.items() if key not in ready}
    check(not pending, "任务依赖存在循环或悬空引用")
    for kind, count in (("FR", 29), ("NFR", 24)):
        expected = {f"{kind}-{i:02}" for i in range(1, count + 1)}
        found = re.findall(rf"^\| ({kind}-\d{{2}}) \|", req, re.M)
        check(len(found) == count and set(found) == expected, f"{kind} 需求定义不完整或重复")
        rows = trace[kind]
        check(len(rows) == count and {r['id'] for r in rows} == expected,
              f"{kind} 追踪项不完整或重复")
        for row in rows:
            check(row["owner"] in ("A", "B"), f"{row['id']}负责人无效")
            check(row["phase"] in ("P0", "P1", "P2", "P3"), f"{row['id']}阶段无效")
            prefix = "AC" if kind == "FR" else "NT"
            check(row["acceptance"] == row["id"].replace(kind, prefix),
                  f"{row['id']}验收映射错误")
            check(row["status"] in ("planned", "in_progress", "verified"),
                  f"{row['id']}状态无效")
            linked = row.get("tasks", [])
            check(bool(linked) and all(task in tasks for task in linked),
                  f"{row['id']}实施任务缺失或不存在")
            known = [tasks[task] for task in linked if task in tasks]
            check(any(task["owner"] == row["owner"] for task in known),
                  f"{row['id']}没有主责人的实施任务")
            check(all(task["phase"] <= row["phase"] for task in known),
                  f"{row['id']}实施任务晚于承诺阶段")
            if kind == "NFR":
                check(bool(known) and row.get("implementation_phase") == min(t["phase"] for t in known),
                      f"{row['id']}首次实施阶段不符")
            else:
                check(f"| {row['module']} |" in architecture, f"{row['id']}模块不存在")
                check(bool(row.get("api")) and all(f"| {route} |" in api for route in row["api"]),
                      f"{row['id']}API映射不存在")
                check(bool(row.get("data")) and all(f"| {table} |" in data for table in row["data"]),
                      f"{row['id']}数据表映射不存在")
            if row["status"] == "verified":
                evidence = row.get("evidence")
                check(bool(evidence) and (ROOT / evidence).is_file(), f"{row['id']}缺少验证报告")
            if kind == "FR":
                check(bool(re.search(rf"^\| {row['id']} \|.*\| {row['owner']} \| {row['phase']} \|$", req, re.M)),
                      f"{row['id']}文档与追踪负责人/阶段不符")
    rules = re.findall(r"^\| (BR-\d{2}) \|", req, re.M)
    check(len(rules) == 17 and set(rules) == {f"BR-{i:02}" for i in range(1, 18)},
          "BR定义不完整或重复")

    if requires_runtime(runtime_files()):
        check((ROOT / "tools/check_all.ps1").is_file(), "业务实现已出现，缺少完整检查入口")

    manifest = json.loads((ROOT / "archive/manifest.json").read_text(encoding="utf-8"))
    expected_archive = {item["path"] for item in manifest["files"]}
    actual_archive = {p.relative_to(ROOT).as_posix() for p in (ROOT / "archive/submissions").rglob("*") if p.is_file()}
    check(actual_archive == expected_archive, "归档文件白名单发生变化")
    for item in manifest["files"]:
        file = (ROOT / item["path"]).resolve()
        check(file.is_relative_to(ROOT / "archive/submissions"), "归档清单路径越界")
        if not file.is_file():
            check(False, f"原件缺失: {item['path']}")
            continue
        data = file.read_bytes()
        check(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
              f"原件哈希变化: {item['path']}")
        if file.suffix == ".zip":
            with zipfile.ZipFile(file) as archive:
                check(archive.testzip() is None, f"ZIP损坏: {file.name}")
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    extracted = (file.parent / member.filename).resolve()
                    safe = extracted.is_relative_to(file.parent)
                    check(safe and extracted.is_file() and extracted.read_bytes() == archive.read(member),
                          f"ZIP与解压文件不一致: {member.filename}")

    print(f"仓库静态检查：{checks} 项，错误 {len(errors)}。")
    for error in errors:
        print(f"- {error}")
    print("范围：文档/追踪/链接/原件完整性；不证明业务、隔离、性能或系统验收。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
