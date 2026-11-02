# ruff: noqa: E402
"""Check real route URLs and exported canonical metadata; behavioral tests are separate."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator

from app.main import create_app
from app.shared.config import Settings

METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
KEYS = ("operationId", "parameters", "requestBody", "responses", "security", "x-roles")


def actual_path(path):
    return path if path.startswith("/health/") else "/api/v1" + path


def compare(app, spec):
    expected = {
        (method.upper(), path): operation
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in METHODS and operation.get("x-implementation") == "implemented"
    }
    registered = {
        (method, actual_path(path)): operation for (method, path), operation in expected.items()
    }
    actual = {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    if set(actual) != set(registered):
        raise ValueError("Implemented API route set differs from canonical contract.")
    exported = app.openapi()
    runtime = {
        (method.upper(), path): operation
        for path, item in exported["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    }
    if set(runtime) != set(expected):
        raise ValueError("FastAPI exported route set differs from actual registration.")
    for (method, path), operation in expected.items():
        route = actual[(method, actual_path(path))]
        expected_status = next(int(code) for code in operation["responses"] if code.startswith("2"))
        if (route.status_code or 200) != expected_status:
            raise ValueError("Registered success status differs from canonical contract.")
        if (route.operation_id or route.unique_id) != operation["operationId"]:
            raise ValueError("Registered operation ID differs from canonical contract.")
        for field in KEYS:
            if runtime[(method, path)].get(field) != operation.get(field):
                raise ValueError(f"Runtime contract differs: {(method, path)} {field}")
        if exported["paths"][path].get("servers") != spec["paths"][path].get("servers"):
            raise ValueError("Runtime path servers differ from canonical contract.")
    if exported.get("servers") != spec.get("servers"):
        raise ValueError("Runtime base URL differs from canonical contract.")
    if exported.get("components") != spec["components"]:
        raise ValueError("Runtime components differ from canonical contract.")
    for schema in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)

    def refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                ref = value["$ref"]
                if not ref.startswith("#/components/"):
                    raise ValueError("Only local component references are permitted.")
                target = spec
                for part in ref[2:].split("/"):
                    target = target[part]
            for item in value.values():
                refs(item)
        elif isinstance(value, list):
            for item in value:
                refs(item)

    refs(spec)
    return len(actual)


def main():
    spec = json.loads((ROOT / "specs/openapi.yaml").read_text(encoding="utf-8"))
    app = create_app(
        Settings(
            "postgresql+psycopg://no-network/astra_contract_test",
            b"contract-check-only-secret-32-bytes",
            "https://contract.invalid",
            "contract-check-only-readiness-32-bytes",
        )
    )
    count = compare(app, spec)
    print(
        f"Canonical API matches {count} registered operations and export metadata; HTTP behavior is checked separately."
    )


if __name__ == "__main__":
    main()
