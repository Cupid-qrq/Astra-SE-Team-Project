from datetime import datetime

from app.modules.identity.domain import require


def assignment_state(value: dict, now: datetime, *, archived: bool = False) -> str:
    if archived:
        return "ARCHIVED"
    if value["published_at"] is None:
        return "DRAFT"
    if now < value["open_at"]:
        return "SCHEDULED"
    if now < value["due_at"]:
        return "OPEN"
    return "CLOSED"


def validate_assignment(value: dict, items: list[dict]) -> None:
    require(bool(value["title"].strip()), "VALIDATION_ERROR", "作业标题不能为空白。", 422)
    require(
        value["open_at"] < value["due_at"], "VALIDATION_ERROR", "开放时间必须早于截止时间。", 422
    )
    require(1 <= len(items) <= 20, "VALIDATION_ERROR", "作业必须包含1—20道题。", 422)
    require(
        len({i["problem_id"] for i in items}) == len(items),
        "VALIDATION_ERROR",
        "作业题目不能重复。",
        422,
    )
    require(
        all(type(i["points"]) is int and i["points"] > 0 for i in items)
        and sum(i["points"] for i in items) == 100,
        "VALIDATION_ERROR",
        "各题分值必须为正整数，总分必须为100。",
        422,
    )


def submission_mode(value: dict, now: datetime, intent: str) -> str:
    state = assignment_state(value, now)
    require(state in ("OPEN", "CLOSED"), "ASSIGNMENT_NOT_OPEN", "作业尚未开放。")
    require(intent in ("FORMAL", "PRACTICE"), "VALIDATION_ERROR", "提交意图无效。", 422)
    require(
        intent != "FORMAL" or state == "OPEN",
        "DEADLINE_PASSED",
        "正式提交已截止，请确认后改用练习提交。",
    )
    return intent
