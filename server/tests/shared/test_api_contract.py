"""Behavioral checks that contract drift is rejected, using the real formal app."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.main import create_app
from app.shared.config import Settings

ROOT = Path(__file__).resolve().parents[3]
module_spec = importlib.util.spec_from_file_location(
    "api_contract_check", ROOT / "tools/check_api_contract.py"
)
checker = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(checker)


def app_and_contract():
    document = json.loads((ROOT / "specs/openapi.yaml").read_text(encoding="utf-8"))
    app = create_app(
        Settings(
            "postgresql+psycopg://no-network/astra_contract_test",
            b"contract-check-only-secret-32-bytes",
            "https://contract.invalid",
            "contract-check-only-readiness-32-bytes",
        )
    )
    return app, document


def test_registered_route_and_schema_drift_are_rejected():
    app, spec = app_and_contract()
    assert checker.compare(app, spec) == 71
    missing_preflight = deepcopy(spec)
    del missing_preflight["paths"]["/preflights/{id}"]
    with pytest.raises(ValueError, match="route set"):
        checker.compare(app, missing_preflight)
    altered = deepcopy(spec)
    altered["paths"]["/courses"]["post"]["responses"]["201"]["content"]["application/json"][
        "schema"
    ] = {"type": "string"}
    with pytest.raises(ValueError, match="Runtime contract differs"):
        checker.compare(app, altered)
    app.add_api_route("/api/v1/undocumented", lambda: {}, methods=["GET"])
    with pytest.raises(ValueError, match="route set"):
        checker.compare(app, spec)


def test_unprefixed_alias_is_not_hidden_by_path_normalization():
    app, spec = app_and_contract()
    operation = deepcopy(spec["paths"]["/problem-profiles"]["get"])
    app.add_api_route(
        "/problem-profiles",
        lambda: {},
        methods=["GET"],
        response_model=None,
        status_code=200,
        operation_id=operation["operationId"],
        openapi_extra=operation,
    )
    with pytest.raises(ValueError, match="route set"):
        checker.compare(app, spec)
