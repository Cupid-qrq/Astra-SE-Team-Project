"""Course-scoped social views reuse the authenticated transactional registrar."""

from app.api.contracts import Cursor
from app.api.teaching import Registrar
from app.modules.identity.domain import require
from app.modules.identity.ports import Record


def register(add: Registrar) -> None:
    def ordered_page(c: Record, rows: list[Record], key: str) -> Record:
        pager: Cursor = c["learning_pager"]
        if pager.after is not None:
            positions = [i for i, row in enumerate(rows) if str(row[key]) == pager.after]
            require(bool(positions), "VALIDATION_ERROR", "列表已更新，请刷新后重试。", 422)
            rows = rows[positions[0] + 1 :]
        return pager.finish(rows[: pager.limit + 1], key)

    def board(c: Record) -> Record:
        value = c["leaderboards"].read(c["actor"], c["path"]["id"], c["query"]["kind"])
        return dict(value, **ordered_page(c, value["items"], "entry_id"))

    def listing(c: Record) -> Record:
        rows = c["discussions"].list(
            c["actor"], c["path"]["id"], c["path"]["problem_id"], c["query"]["version_id"]
        )
        rows.sort(
            key=lambda row: (row["pinned"], row["created_at"], row["thread_id"]), reverse=True
        )
        return ordered_page(c, rows, "thread_id")

    def detail(c: Record) -> Record:
        value = c["discussions"].read(c["actor"], c["path"]["id"])
        replies = sorted(value["replies"], key=lambda row: (row["created_at"], row["reply_id"]))
        page = ordered_page(c, replies, "reply_id")
        return dict(thread=value["thread"], replies=page["items"], next_cursor=page["next_cursor"])

    add("GET", "/courses/{id}/leaderboard", board)
    add(
        "PATCH",
        "/courses/{id}/leaderboard-preference",
        lambda c: c["leaderboards"].preference(c["actor"], c["path"]["id"], c["body"]),
    )
    add("GET", "/courses/{id}/problems/{problem_id}/discussions", listing)
    add(
        "POST",
        "/courses/{id}/problems/{problem_id}/discussions",
        lambda c: c["discussions"].create(
            c["actor"], c["path"]["id"], c["path"]["problem_id"], c["body"]
        ),
    )
    add("GET", "/discussions/{id}", detail)
    add(
        "POST",
        "/discussions/{id}/replies",
        lambda c: c["discussions"].reply(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "PATCH",
        "/discussions/{id}",
        lambda c: c["discussions"].update(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "PATCH",
        "/discussion-replies/{id}",
        lambda c: c["discussions"].update_reply(c["actor"], c["path"]["id"], c["body"]),
    )
