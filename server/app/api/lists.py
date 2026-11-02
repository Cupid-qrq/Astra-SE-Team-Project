"""Authorized, bounded SQL lists. Internal Repository.rows remains complete."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import String, case, func, literal, select
from sqlalchemy.engine import Connection
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from app.api.contracts import Cursor
from app.modules.courses.application import public_course
from app.modules.identity.application import public_user
from app.modules.identity.domain import Fault, require, role
from app.modules.identity.ports import Record
from app.modules.learning.feedback import catalog_summary, version_summary
from app.modules.learning.templates import template_summary, template_version_summary
from app.shared.metadata import metadata


def sql_list(c: Record, path: str, pager: Cursor) -> Record | None:
    actor, query, cid = c["actor"], c["query"], c["path"].get("id")
    tables = metadata.tables
    courses, members, users = (tables[name] for name in ("courses", "course_members", "users"))
    problems, versions, assignments = (
        tables[name] for name in ("problems", "problem_versions", "assignments")
    )
    connection: Connection = c["repo"].connection
    statement: Select[Any]
    key: ColumnElement[Any]
    projection: Callable[[Record], Record] | None = None
    if path == "/courses":
        role(actor, ("TEACHER", "STUDENT"))
        statement = select(courses)
        if actor["role"] == "TEACHER":
            statement = statement.where(courses.c.teacher_id == actor["user_id"])
        else:
            statement = statement.join(members, members.c.course_id == courses.c.course_id).where(
                members.c.user_id == actor["user_id"], members.c.status == "ACTIVE"
            )
        if "status" in query:
            statement = statement.where(courses.c.status == query["status"])
        key, projection = courses.c.course_id, public_course
    elif path == "/courses/{id}/members":
        c["courses"].access(actor, cid, teacher=True)
        statement = (
            select(members.c.user_id, users.c.display_name, members.c.status)
            .join(users, members.c.user_id == users.c.user_id)
            .where(members.c.course_id == cid)
        )
        if "status" in query:
            statement = statement.where(members.c.status == query["status"])
        key = members.c.user_id
    elif path == "/courses/{id}/problems":
        c["courses"].access(actor, cid, teacher=True)
        published = (
            select(versions.c.version_id)
            .where(
                versions.c.problem_id == problems.c.problem_id, versions.c.published_at.is_not(None)
            )
            .exists()
        )
        title = (
            select(versions.c.title)
            .where(versions.c.problem_id == problems.c.problem_id)
            .order_by(versions.c.version_no.desc())
            .limit(1)
            .scalar_subquery()
        )
        state = case((published, "PUBLISHED"), else_="DRAFT")
        fields = (
            "problem_id",
            "canonical_problem_id",
            "owner_course_id",
            "practice_released",
            "practice_version_id",
            "revision",
        )
        statement = select(
            *(problems.c[name] for name in fields),
            func.coalesce(title, "未命名题目").label("title"),
            state.label("status"),
        ).where(problems.c.owner_course_id == cid)
        if "status" in query:
            statement = statement.where(state == query["status"])
        if "tag" in query:
            statement = statement.where(
                select(versions.c.version_id)
                .where(
                    versions.c.problem_id == problems.c.problem_id,
                    versions.c.tags.contains([query["tag"]]),
                )
                .exists()
            )
        key = problems.c.problem_id
    elif path == "/problems/{id}/versions":
        c["problems"].problem(actor, cid)
        statement = select(versions).where(versions.c.problem_id == cid)
        if "status" in query:
            statement = statement.where(
                versions.c.published_at.is_(None)
                if query["status"] == "DRAFT"
                else versions.c.published_at.is_not(None)
            )
        if "tag" in query:
            statement = statement.where(versions.c.tags.contains([query["tag"]]))
        key, projection = versions.c.version_id, c["problems"].view
    elif path == "/courses/{id}/assignments":
        course = c["courses"].access(actor, cid)
        now = c["repo"].now()
        state = case(
            (literal(course["status"] == "ARCHIVED"), "ARCHIVED"),
            (assignments.c.published_at.is_(None), "DRAFT"),
            (assignments.c.open_at > now, "SCHEDULED"),
            (assignments.c.due_at > now, "OPEN"),
            else_="CLOSED",
        )
        statement = select(assignments).where(assignments.c.course_id == cid)
        if actor["role"] == "STUDENT":
            statement = statement.where(assignments.c.published_at.is_not(None))
        if "state" in query:
            statement = statement.where(state == query["state"])
        key = assignments.c.assignment_id

        def summary(row: Record) -> Record:
            return c["assignments"].summary(row, course)  # type: ignore[no-any-return]

        projection = summary
    elif path in ("/feedback-catalogs", "/hint-templates"):
        role(actor, ("TEACHER", "ADMIN"))
        is_template = path == "/hint-templates"
        catalogs = tables["template_catalogs" if is_template else "feedback_catalogs"]
        statement = select(catalogs)
        if actor["role"] == "ADMIN":
            require("course_id" not in query, "FORBIDDEN", "管理员只能维护全局内容。", 403)
            statement = statement.where(catalogs.c.scope_key == "GLOBAL")
        else:
            if "course_id" in query:
                c["courses"].access(actor, query["course_id"], teacher=True)
            statement = statement.join(
                courses,
                catalogs.c.scope_key == literal("COURSE:") + courses.c.course_id.cast(String),
            ).where(courses.c.teacher_id == actor["user_id"])
            if "course_id" in query:
                statement = statement.where(courses.c.course_id == query["course_id"])
        if is_template:
            key, projection = catalogs.c.template_id, template_summary
        else:
            key, projection = catalogs.c.catalog_id, catalog_summary
    elif path == "/feedback-catalogs/{id}/versions":
        c["learning"].managed_catalog(actor, cid)
        feedback_versions = tables["feedback_versions"]
        statement = select(feedback_versions).where(feedback_versions.c.catalog_id == cid)
        key, projection = feedback_versions.c.version_id, version_summary
    elif path == "/hint-templates/{id}/versions":
        c["learning"].templates.managed("template_catalogs", actor, cid)
        versions = tables["template_versions"]
        statement = select(versions).where(versions.c.template_id == cid)
        key, projection = versions.c.version_id, template_version_summary
    elif path == "/admin/users":
        role(actor, ("ADMIN",))
        statement = select(users)
        for name in ("login_name", "role", "status"):
            if name in query:
                statement = statement.where(users.c[name] == query[name])
        key, projection = users.c.user_id, public_user
    else:
        return None
    if pager.after is not None:
        try:
            UUID(pager.after)
        except ValueError:
            raise Fault(422, "VALIDATION_ERROR", "游标无效。") from None
        require(
            connection.execute(statement.where(key == pager.after).limit(1)).first() is not None,
            "VALIDATION_ERROR",
            "游标已失效。",
            422,
        )
        statement = statement.where(key > pager.after)
    rows = [
        dict(row)
        for row in connection.execute(statement.order_by(key).limit(pager.limit + 1)).mappings()
    ]
    key_name = key.key
    if projection is not None:
        rows = [projection(row) for row in rows]
    return pager.finish(rows, key_name)
