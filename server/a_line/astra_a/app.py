"""Injectable A validation app, NOT the B-owned production entrypoint.

No auto-seeding, schema creation, credentials or synthetic preflight on startup.
"""

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from app.modules.assignments.api import register as assignment_routes
from app.modules.assignments.application import Assignments
from app.modules.courses.application import Courses, public_course
from app.modules.identity.application import Identity, public_user
from app.modules.identity.domain import Fault, require, role
from app.modules.learning.api import register as learning_routes
from app.modules.learning.application import Learning
from app.modules.problems.api import register as problem_routes
from app.modules.problems.application import Problems
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .contracts import SPEC, page, validate
from .security import ArgonPasswords
from .storage import SqlRepository


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def create_app(
    engine,
    effects,
    *,
    secret: bytes,
    origin: str,
    clock: Callable | None = None,
    preflight=None,
    profiles=None,
    assignment_guard=None,
    submission_query=None,
    feedback_submissions=None,
) -> FastAPI:
    require(len(secret) >= 32, "CONFIGURATION_ERROR", "会话密钥至少32字节。", 500)
    require(origin.startswith("https://"), "CONFIGURATION_ERROR", "验证应用要求HTTPS来源。", 500)
    app = FastAPI(title="Astra A validation", docs_url=None, redoc_url=None)
    passwords = ArgonPasswords()
    routes: list[tuple[str, str, Callable]] = []

    def route(method, path, handler):
        routes.append((method, path, handler))

    route("GET", "/auth/session", lambda c: c["identity"].session(c["token"]))
    route("POST", "/auth/login", lambda c: c["identity"].login(c["token"], c["body"], c["source"]))
    route("POST", "/auth/logout", lambda c: c["identity"].logout(c["token"]))
    route("POST", "/auth/password", lambda c: c["identity"].password(c["actor"], c["body"]))
    route("GET", "/courses", lambda c: c["page"](c["courses"].visible(c["actor"]), "course_id"))
    route("POST", "/courses", lambda c: c["courses"].create(c["actor"], c["body"]))
    route(
        "GET",
        "/courses/{id}",
        lambda c: public_course(c["courses"].access(c["actor"], c["path"]["id"])),
    )
    route(
        "PATCH",
        "/courses/{id}",
        lambda c: {
            "revision": c["courses"].update(c["actor"], c["path"]["id"], c["body"])["revision"]
        },
    )
    route(
        "GET",
        "/courses/{id}/members",
        lambda c: c["page"](c["courses"].members(c["actor"], c["path"]["id"]), "user_id"),
    )
    route(
        "PUT",
        "/courses/{id}/members/{user_id}",
        lambda c: c["courses"].member(c["actor"], c["path"]["id"], c["path"]["user_id"], c["body"]),
    )

    def users(c):
        role(c["actor"], ("ADMIN",))
        return c["page"]([public_user(u) for u in c["repo"].rows("users")], "user_id")

    route("GET", "/admin/users", users)
    route("POST", "/admin/users", lambda c: c["identity"].create_user(c["actor"], c["body"]))
    route(
        "PATCH",
        "/admin/users/{id}",
        lambda c: {
            "revision": c["identity"].update_user(c["actor"], c["path"]["id"], c["body"])[
                "revision"
            ]
        },
    )

    def reset(c):
        c["identity"].update_user(c["actor"], c["path"]["id"], c["body"], reset=True)

    route("POST", "/admin/users/{id}/reset-password", reset)

    def unavailable_list(c, teacher):
        c["courses"].access(c["actor"], c["path"]["id"], teacher=teacher)
        raise Fault(503, "INTEGRATION_UNAVAILABLE", "服务尚未接入。", retry=5)

    def runtime_profiles(c):
        role(c["actor"], ("TEACHER",))
        if profiles is None:
            raise Fault(503, "PROFILE_UNAVAILABLE", "运行环境尚未配置，请联系管理员。", retry=5)
        return c["page"](profiles, "profile_id")

    route("GET", "/problem-profiles", runtime_profiles)
    problem_routes(route)
    assignment_routes(route)
    learning_routes(route)

    def error_response(error: Fault, request_id: str) -> JSONResponse:
        return JSONResponse(
            dict(
                code=error.code,
                message=error.message,
                request_id=request_id,
                retryable=error.retry is not None,
                retry_after_seconds=error.retry,
                field_errors=error.fields,
            ),
            status_code=error.status,
            headers={
                "X-Request-Id": request_id,
                "Cache-Control": "no-store",
                **({"Retry-After": str(error.retry)} if error.retry is not None else {}),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response(
            Fault(
                error.status_code,
                "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR",
                "请求路径或方法不可用。",
            ),
            str(uuid4()),
        )

    def endpoint(method: str, path: str, handler):
        operation = SPEC["paths"].get(path, {}).get(method.lower())
        if operation is None:
            raise ValueError(f"Missing contract: {method} {path}")
        success = next(int(k) for k in operation["responses"] if k.startswith("2"))

        def perform(request: Request, raw: bytes, request_id: str):
            with engine.connect() as connection:
                tx = connection.begin()
                try:
                    connection.exec_driver_sql("SET LOCAL lock_timeout = '1500ms'")
                    connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
                    repo = SqlRepository(connection, clock)
                    repo.guard()
                    identity = Identity(repo, passwords, effects, secret)
                    token = request.cookies.get("astra_session")
                    auth_path = path in ("/auth/session", "/auth/login")
                    actor = (
                        None
                        if auth_path
                        else identity.actor(
                            token,
                            allow_password=path in ("/auth/password", "/auth/logout"),
                            activity=not (
                                method == "GET" and request.headers.get("X-Astra-Background") == "1"
                            ),
                        )
                    )
                    if method not in ("GET", "HEAD"):
                        identity.check_csrf(
                            token,
                            request.headers.get("X-CSRF-Token"),
                            request.headers.get("Origin"),
                            origin,
                        )
                    body = None
                    if "requestBody" in operation:
                        try:
                            body = json.loads(raw, object_pairs_hook=unique_object)
                        except (ValueError, UnicodeDecodeError):
                            raise Fault(
                                422, "VALIDATION_ERROR", "请求必须为有效UTF-8 JSON。"
                            ) from None
                        validate(
                            operation["requestBody"]["content"]["application/json"]["schema"], body
                        )
                    elif raw:
                        raise Fault(422, "VALIDATION_ERROR", "该操作不接受请求正文。")
                    allowed_query = {
                        p["name"] for p in operation.get("parameters", []) if p.get("in") == "query"
                    }
                    require(
                        not (set(request.query_params) - allowed_query),
                        "VALIDATION_ERROR",
                        "未知查询参数。",
                        422,
                    )
                    require(
                        len(request.query_params.multi_items()) == len(request.query_params),
                        "VALIDATION_ERROR",
                        "查询参数不得重复。",
                        422,
                    )
                    for parameter in operation.get("parameters", []):
                        if (
                            parameter.get("in") == "query"
                            and parameter["name"] in request.query_params
                        ):
                            value = request.query_params[parameter["name"]]
                            schema = parameter["schema"]
                            if schema.get("type") == "integer":
                                require(
                                    value.isascii() and value.isdigit(),
                                    "VALIDATION_ERROR",
                                    "查询数值无效。",
                                    422,
                                )
                                validate(schema, int(value))
                            else:
                                validate(schema, value)
                    for key, value in request.path_params.items():
                        if key in ("id", "user_id", "problem_id"):
                            try:
                                UUID(value)
                            except ValueError:
                                raise Fault(422, "VALIDATION_ERROR", "对象编号格式无效。") from None
                    context: dict[str, Any] = dict(
                        repo=repo,
                        learning=Learning(repo, effects, feedback_submissions),
                        assignments=Assignments(repo, effects, assignment_guard),
                        problems=Problems(repo, effects, preflight),
                        identity=identity,
                        courses=Courses(repo, effects),
                        actor=actor,
                        token=token,
                        body=body,
                        path=request.path_params,
                        query=dict(request.query_params),
                        source=request.client.host if request.client else "unknown",
                    )

                    def paginated(rows, key):
                        filters = {
                            k: v
                            for k, v in request.query_params.items()
                            if k not in ("cursor", "limit", "tag")
                        }
                        rows = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
                        return page(
                            rows,
                            key,
                            {
                                k: v
                                for k, v in request.query_params.items()
                                if k in ("cursor", "limit")
                            },
                            (actor["user_id"] if actor else "anonymous")
                            + str(request.url.path)
                            + json.dumps(
                                {
                                    k: v
                                    for k, v in request.query_params.items()
                                    if k not in ("cursor", "limit")
                                },
                                sort_keys=True,
                            ),
                            secret,
                        )

                    context["page"] = paginated
                    result = handler(context)
                    new_cookie = None
                    if path in ("/auth/session", "/auth/login"):
                        result, new_cookie = result
                    response_schema = (
                        operation["responses"][str(success)]
                        .get("content", {})
                        .get("application/json", {})
                        .get("schema")
                    )
                    if response_schema:
                        try:
                            validate(response_schema, result)
                        except Fault:
                            raise Fault(500, "RESPONSE_CONTRACT_ERROR", "响应校验失败。") from None
                    tx.commit()
                    response = (
                        Response(status_code=success)
                        if success == 204
                        else JSONResponse(result, status_code=success)
                    )
                    response.headers.update(
                        {"X-Request-Id": request_id, "Cache-Control": "no-store"}
                    )
                    if new_cookie:
                        response.set_cookie(
                            "astra_session",
                            new_cookie,
                            httponly=True,
                            secure=True,
                            samesite="lax",
                            path="/",
                            max_age=8 * 3600,
                        )
                    if path in ("/auth/logout", "/auth/password"):
                        response.delete_cookie(
                            "astra_session", path="/", secure=True, httponly=True, samesite="lax"
                        )
                    return response
                except Fault as error:
                    if error.commit:
                        tx.commit()
                    else:
                        tx.rollback()
                    return error_response(error, request_id)
                except IntegrityError:
                    tx.rollback()
                    return error_response(
                        Fault(409, "CONSTRAINT_CONFLICT", "数据冲突，请刷新后重试。"), request_id
                    )
                except OperationalError:
                    tx.rollback()
                    return error_response(
                        Fault(503, "DATABASE_UNAVAILABLE", "数据库暂不可用，请稍后重试。", retry=2),
                        request_id,
                    )
                except Exception:
                    tx.rollback()
                    return error_response(
                        Fault(500, "INTERNAL_ERROR", "服务暂时不可用。"), request_id
                    )

        async def handle(request: Request):
            request_id = request.headers.get("X-Request-Id", "")
            try:
                request_id = str(UUID(request_id))
            except ValueError:
                request_id = str(uuid4())
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 512 * 1024:
                    return error_response(
                        Fault(413, "PAYLOAD_TOO_LARGE", "请求正文超过上限。"), request_id
                    )
            try:
                return await run_in_threadpool(perform, request, bytes(raw), request_id)
            except OperationalError:
                return error_response(
                    Fault(503, "DATABASE_UNAVAILABLE", "数据库暂不可用，请稍后重试。", retry=2),
                    request_id,
                )

        return handle

    for method, path, handler in routes:
        app.add_api_route("/api/v1" + path, endpoint(method, path, handler), methods=[method])
    # Runtime validates both directions against these canonical schemas.
    runtime_document = {
        **SPEC,
        "paths": {
            p: {m.lower(): SPEC["paths"][p][m.lower()] for m, q, _ in routes if p == q}
            for _, p, _ in routes
        },
    }
    # Public FastAPI extension hook: assigning only the cache is invalidated by
    # route-version tracking in recent FastAPI releases.
    app.openapi = lambda: runtime_document  # type: ignore[method-assign]
    return app
