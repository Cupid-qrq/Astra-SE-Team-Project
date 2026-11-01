"""Bind A application services to the formal HTTP composition."""

from collections.abc import Callable
from typing import Any, cast

from app.modules.assignments.api import register as assignment_routes
from app.modules.courses.application import public_course
from app.modules.identity.domain import Fault, role
from app.modules.identity.ports import Record
from app.modules.learning.api import register as learning_routes
from app.modules.problems.api import register as problem_routes

Handler = Callable[[Record], Any]
Registrar = Callable[[str, str, Handler], None]


def register(add: Registrar, profiles: tuple[Record, ...]) -> None:
    add("GET", "/auth/session", lambda c: c["identity"].session(c["token"]))
    add("POST", "/auth/login", lambda c: c["identity"].login(c["token"], c["body"], c["source"]))
    add("POST", "/auth/logout", lambda c: c["identity"].logout(c["token"]))
    add("POST", "/auth/password", lambda c: c["identity"].password(c["actor"], c["body"]))
    # Large lists are intercepted by the authorized SQL adapter before these callbacks.
    add("GET", "/courses", lambda c: None)
    add("POST", "/courses", lambda c: c["courses"].create(c["actor"], c["body"]))
    add(
        "GET",
        "/courses/{id}",
        lambda c: public_course(c["courses"].access(c["actor"], c["path"]["id"])),
    )
    add(
        "PATCH",
        "/courses/{id}",
        lambda c: {
            "revision": c["courses"].update(c["actor"], c["path"]["id"], c["body"])["revision"]
        },
    )
    add("GET", "/courses/{id}/members", lambda c: None)
    add(
        "PUT",
        "/courses/{id}/members/{user_id}",
        lambda c: c["courses"].member(c["actor"], c["path"]["id"], c["path"]["user_id"], c["body"]),
    )
    add("GET", "/admin/users", lambda c: None)
    add("POST", "/admin/users", lambda c: c["identity"].create_user(c["actor"], c["body"]))
    add(
        "PATCH",
        "/admin/users/{id}",
        lambda c: {
            "revision": c["identity"].update_user(c["actor"], c["path"]["id"], c["body"])[
                "revision"
            ]
        },
    )
    add(
        "POST",
        "/admin/users/{id}/reset-password",
        lambda c: c["identity"].update_user(c["actor"], c["path"]["id"], c["body"], reset=True),
    )

    def runtime_profiles(c: Record) -> Record:
        role(c["actor"], ("TEACHER",))
        if not profiles:
            raise Fault(503, "PROFILE_UNAVAILABLE", "运行环境尚未配置，请联系管理员。", retry=5)
        return c["page"](list(profiles), "profile_id")  # type: ignore[no-any-return]

    add("GET", "/problem-profiles", runtime_profiles)
    for routes in (problem_routes, assignment_routes, learning_routes):
        cast(Callable[[Registrar], None], routes)(add)
