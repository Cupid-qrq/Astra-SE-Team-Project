from datetime import timedelta
from uuid import uuid4

from astra_a.storage import SqlRepository
from test_hint_store import setup_hint

from app.modules.learning.hint_service import HintService


def test_history_is_private_paged_and_contains_only_receipt_identifiers(env):
    source, model, actor, body = setup_hint(env)
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        _, receipt = HintService(repo, source, model).create(actor, body)
        first = repo.get("ai_hints", receipt["hint_id"])
        second = str(uuid4())
        repo.add(
            "ai_hints",
            {
                **first,
                "hint_id": second,
                "request_key": str(uuid4()),
                "status": "FAILED",
                "created_at": env.clock() + timedelta(seconds=1),
            },
        )
        repo.add(
            "ai_hints",
            {
                **first,
                "hint_id": str(uuid4()),
                "request_key": str(uuid4()),
                "user_id": env.users["student_b"],
            },
        )
    route = "/api/v1/ai-hints"
    student = env.login("student_a")
    page = student.get(route, params={"limit": 1})
    assert page.status_code == 200, page.text
    entry = page.json()["items"][0]
    assert entry["hint_id"] == second and set(entry) == {"hint_id", "created_at"}
    cursor = page.json()["next_cursor"]
    last = student.get(route, params={"cursor": cursor, "limit": 1}).json()
    assert last["next_cursor"] is None and last["items"][0]["hint_id"] == first["hint_id"]
    assert env.login("student_b").get(route, params={"cursor": cursor}).status_code == 422
    assert env.login("teacher_a").get(route).status_code == 403
