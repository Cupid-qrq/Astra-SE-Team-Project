"""Safe, uniform HTTP errors. Never serialize exceptions or rejected input."""

from fastapi.responses import JSONResponse

from app.modules.identity.domain import Fault


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
