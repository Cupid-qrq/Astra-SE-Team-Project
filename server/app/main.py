"""Formal HTTP entrypoint. Startup never creates schema or seeds business data."""

import hmac
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from app.adapters.judge_profiles import SnapshotCatalog
from app.api.contracts import Contract, Cursor, parse_body
from app.api.errors import error_response
from app.api.lists import sql_list
from app.api.preflights import register as register_preflights
from app.api.teaching import Handler, register
from app.modules.assignments.application import Assignments
from app.modules.courses.application import Courses
from app.modules.identity.application import Identity
from app.modules.identity.domain import Fault
from app.modules.identity.ports import Record
from app.modules.judging.preflight import TransactionalPreflight
from app.modules.learning.application import Learning
from app.modules.learning.hint_service import HintService, Sources
from app.modules.learning.student import LearningResults, StudentLearning
from app.modules.problems.application import Problems
from app.shared.config import Settings
from app.shared.database import create_database_engine
from app.shared.effects import TransactionalEffects
from app.shared.passwords import ArgonPasswords
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    learning_results: LearningResults | None = None,
    hint_sources: Sources | None = None,
    hint_configuration: str | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    owned = engine is None
    database = engine if engine is not None else create_database_engine(settings.database_url)
    configuration = settings
    contract, passwords = Contract.load(), ArgonPasswords()
    for profile in settings.profiles:
        contract.validate({"$ref": "#/components/schemas/Profile"}, profile)

    preflight_catalog = SnapshotCatalog(settings.profiles) if settings.profiles else None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owned:
                database.dispose()

    app = FastAPI(
        title=contract.document["info"]["title"],
        version=contract.document["info"]["version"],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def protocol(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            request_id = str(UUID(request.headers.get("X-Request-Id", "")))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        protected = ("Origin", "X-CSRF-Token", "X-Request-Id", "X-Astra-Background", "Content-Type")
        if any(len(request.headers.getlist(name)) > 1 for name in protected):
            return error_response(Fault(400, "INVALID_REQUEST", "请求头不得重复。"), request_id)
        try:
            response = await call_next(request)
        except Exception:
            response = error_response(Fault(500, "INTERNAL_ERROR", "服务暂时不可用。"), request_id)
        response.headers.update({"X-Request-Id": request_id, "Cache-Control": "no-store"})
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return error_response(
            Fault(
                error.status_code,
                "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR",
                "请求路径或方法不可用。",
            ),
            request.state.request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return error_response(
            Fault(422, "VALIDATION_ERROR", "请求参数无效。"), request.state.request_id
        )

    @app.get(
        "/health/live",
        response_model=None,
        operation_id="health_live",
        openapi_extra=deepcopy(contract.document["paths"]["/health/live"]["get"]),
    )
    def liveness() -> Record:
        return {"status": "live"}

    @app.get(
        "/health/ready",
        response_model=None,
        operation_id="health_ready",
        openapi_extra=deepcopy(contract.document["paths"]["/health/ready"]["get"]),
    )
    def readiness(request: Request) -> Response:
        supplied = request.headers.get("X-Readiness-Token", "")
        if not hmac.compare_digest(supplied.encode(), configuration.readiness_token.encode()):
            return error_response(
                Fault(403, "FORBIDDEN", "健康检查凭据无效。"), request.state.request_id
            )
        try:
            with database.connect() as connection:
                connection.exec_driver_sql("SET LOCAL statement_timeout = '1500ms'")
                head = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()
                if head != "b008":
                    raise ValueError("Migration is not current")
            return JSONResponse({"status": "ready"})
        except (SQLAlchemyError, ValueError):
            return error_response(
                Fault(503, "PERSISTENCE_UNAVAILABLE", "服务尚未就绪。", retry=2),
                request.state.request_id,
            )

    def endpoint(
        method: str, path: str, handler: Handler, operation: Record
    ) -> Callable[[Request], Awaitable[Response]]:
        default_success = next(int(k) for k in operation["responses"] if k.startswith("2"))

        def perform(request: Request, body: object) -> Response:
            success = default_success
            request_id = request.state.request_id
            new_cookie: str | None = None
            failure = None
            try:
                with UnitOfWork(database) as connection:
                    connection.exec_driver_sql("SET LOCAL lock_timeout = '1500ms'")
                    connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
                    repo = SqlRepository(connection)
                    repo.guard()
                    effects = TransactionalEffects(repo, request_id)
                    identity = Identity(repo, passwords, effects, configuration.session_secret)
                    token = request.cookies.get("astra_session")
                    actor = (
                        None
                        if path in ("/auth/session", "/auth/login")
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
                            configuration.origin,
                        )
                    contract.request(operation, request, body)
                    query = dict(request.query_params)
                    filters = {k: v for k, v in query.items() if k not in ("cursor", "limit")}
                    scope = json.dumps(
                        [
                            actor["user_id"] if actor else "anonymous",
                            str(request.url.path),
                            filters,
                        ],
                        sort_keys=True,
                    )
                    pager = Cursor(query, scope, configuration.session_secret)
                    preflight = TransactionalPreflight(repo, preflight_catalog, effects)
                    context: Record = dict(
                        repo=repo,
                        identity=identity,
                        courses=Courses(repo, effects),
                        problems=Problems(repo, effects, preflight),
                        preflight=preflight,
                        assignments=Assignments(repo, effects),
                        hints=HintService(repo, hint_sources, hint_configuration),
                        learning=Learning(repo, effects),
                        actor=actor,
                        token=token,
                        body=body,
                        path=request.path_params,
                        query=query,
                        page=pager.bounded,
                        learning_pager=pager,
                        student_learning=StudentLearning(
                            connection, repo, effects, learning_results
                        ),
                        source=request.client.host if request.client else "unknown",
                    )
                    try:
                        result: Any = sql_list(context, path, pager) if method == "GET" else None
                        if result is None:
                            result = handler(context)
                        if path in ("/auth/session", "/auth/login"):
                            result, new_cookie = result
                        elif path == "/ai-hints" and method == "POST":
                            success, result = result
                        contract.response(operation, success, result)
                    except Fault as error:
                        # A's failed-login ledger must commit; all other faults escape and roll back.
                        if not error.commit:
                            raise
                        failure = error
                # Response/cookie is emitted only after a successful transaction exit.
                if failure is not None:
                    return error_response(failure, request_id)
                response = (
                    Response(status_code=204)
                    if success == 204
                    else JSONResponse(result, status_code=success)
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
                return error_response(error, request_id)

            except (SQLAlchemyError, PoolTimeout):
                return error_response(
                    Fault(503, "PERSISTENCE_UNAVAILABLE", "数据库暂不可用，请稍后重试。", retry=2),
                    request_id,
                )
            except Exception:
                return error_response(Fault(500, "INTERNAL_ERROR", "服务暂时不可用。"), request_id)

        async def handle(request: Request) -> Response:
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 512 * 1024:
                    return error_response(
                        Fault(413, "PAYLOAD_TOO_LARGE", "请求正文超过上限。"),
                        request.state.request_id,
                    )
                raw.extend(chunk)
            try:
                body = parse_body(bytes(raw), operation, request.headers.get("Content-Type", ""))
            except Fault as error:
                return error_response(error, request.state.request_id)
            return await run_in_threadpool(perform, request, body)

        return handle

    def add(method: str, path: str, handler: Handler) -> None:
        operation = contract.document["paths"][path][method.lower()]
        app.add_api_route(
            "/api/v1" + path,
            endpoint(method, path, handler, operation),
            methods=[method],
            response_model=None,
            status_code=next(int(k) for k in operation["responses"] if k.startswith("2")),
            operation_id=operation["operationId"],
            openapi_extra=deepcopy(operation),
        )

    register(add, settings.profiles)
    register_preflights(add)

    def export_openapi() -> Record:
        document = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            openapi_version=contract.document["openapi"],
        )
        # Route registration determines what is exported. Schemas are contract-first metadata.
        # Canonical paths are relative to /api/v1; health explicitly uses the service root.
        paths: Record = {}
        for url, item in document["paths"].items():
            relative = url.removeprefix("/api/v1") if url.startswith("/api/v1/") else url
            paths[relative] = item
            canonical_item = contract.document["paths"].get(relative, {})
            if "servers" in canonical_item:
                item["servers"] = deepcopy(canonical_item["servers"])
        document["paths"] = paths
        document["components"] = deepcopy(contract.document["components"])
        document["servers"] = deepcopy(contract.document["servers"])
        return document

    app.openapi = export_openapi  # type: ignore[method-assign]
    app.state.contract = contract
    return app
