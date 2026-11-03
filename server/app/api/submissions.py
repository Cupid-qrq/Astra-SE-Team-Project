"""Authenticated submission admission and safe result projections."""

from app.api.teaching import Registrar


def register(add: Registrar) -> None:
    add(
        "POST",
        "/submissions",
        lambda c: c["submissions"].accept(
            c["actor"],
            c["body"],
            c["headers"].get("Idempotency-Key"),
            c["headers"].get("X-Submission-Intent"),
            c["request_id"],
        ),
    )
    add(
        "GET",
        "/submissions",
        lambda c: c["submissions"].history(c["actor"], c["query"], c["learning_pager"]),
    )
    add("GET", "/submissions/{id}", lambda c: c["submissions"].detail(c["actor"], c["path"]["id"]))
    add(
        "GET",
        "/submissions/{id}/attempts",
        lambda c: c["submissions"].rounds(c["actor"], c["path"]["id"], c["learning_pager"]),
    )

    add(
        "GET",
        "/assignments/{id}/submissions",
        lambda c: c["submissions"].history(
            c["actor"], dict(c["query"], assignment_id=c["path"]["id"]), c["learning_pager"]
        ),
    )
