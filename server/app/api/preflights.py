"""B-owned preflight routes, sharing the caller's authenticated transaction."""

from app.api.teaching import Registrar
from app.modules.identity.domain import revision
from app.modules.identity.ports import Record


def register(add: Registrar) -> None:
    def enqueue(context: Record) -> Record:
        version = context["problems"].version(context["actor"], context["path"]["id"], write=True)
        revision(version, context["body"]["expected_revision"])
        return dict(
            context["preflight"].enqueue(context["repo"], context["actor"], version["version_id"])
        )

    add("POST", "/problem-versions/{id}/preflight", enqueue)
    add(
        "GET",
        "/preflights/{id}",
        lambda c: c["preflight"].read(c["repo"], c["actor"], c["path"]["id"]),
    )
