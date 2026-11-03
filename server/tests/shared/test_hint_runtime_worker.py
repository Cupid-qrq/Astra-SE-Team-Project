import asyncio
import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event
from test_http import http_env as http_env
from test_model_runtime import load_profile

from app.main import create_app
from app.modules.learning.application import seed_global_feedback
from app.modules.learning.hint_service import HintService
from app.modules.learning.hint_worker import bootstrap, build_worker
from app.modules.learning.policy_rules import HintSource
from app.shared.metadata import metadata
from app.shared.repository import SqlRepository


def setup_job(http_env, profile):
    engine, ids, _, _ = http_env
    submission, catalog, version = [str(uuid4()) for _ in range(3)]
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        repo.guard()
        repo.change("assignments", ids["assignment"], ai_policy="GUIDED")
        feedback = seed_global_feedback(repo, ids["admin"])["WA"]
        repo.add(
            "template_catalogs",
            dict(template_id=catalog, scope_key="GLOBAL", draft_payload={}, draft_revision=1),
        )
        repo.add(
            "template_versions",
            dict(
                version_id=version,
                template_id=catalog,
                version_no=1,
                body="检查 {verdict}",
                allowed_placeholders=["verdict"],
                schema_version="1",
                author_id=ids["admin"],
                published_at=repo.now(),
                checksum="a" * 64,
            ),
        )
        repo.change("template_catalogs", catalog, active_version_id=version)

    class Sources:
        def hint_source(self, repo, uid, sid):
            return HintSource(
                submission,
                ids["student"],
                ids["course"],
                ids["problem"],
                "FINISHED",
                "WA",
                feedback,
                "basis",
                "attempt",
                "version",
            )

        def hint_context(self, repo, source):
            return dict(
                public_problem="求和",
                public_samples=[dict(input="1 2", output="3")],
                student_code="print(2)",
                language_key="python3",
                sanitized_diagnostic="",
                verdict="WA",
            )

    source = Sources()
    with engine.begin() as connection:
        service = HintService(SqlRepository(connection), source, profile.config_id)
        _, body = service.create(
            dict(user_id=ids["student"], role="STUDENT"),
            dict(submission_id=submission, data_sharing_consent=True, request_key=str(uuid4())),
        )
    return source, body["hint_id"]


def test_bootstrap_tightens_budget_preserving_history_and_rejects_drift(http_env, tmp_path):
    engine = http_env[0]
    profile = load_profile(tmp_path)
    before = set(metadata.tables)
    with engine.begin() as connection:
        SqlRepository(connection).add(
            "budget_accounts",
            dict(
                scope_key="PROJECT",
                limit_amount=500,
                settled_amount=3,
                reserved_amount=4,
                uncertain_amount=5,
                revision=7,
            ),
        )
    bootstrap(engine, profile)
    bootstrap(engine, profile)
    assert set(metadata.tables) == before
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        account = repo.get("budget_accounts", "PROJECT")
        assert account["limit_amount"] == 20
        assert (
            account["settled_amount"],
            account["reserved_amount"],
            account["uncertain_amount"],
            account["revision"],
        ) == (3, 4, 5, 8)
    with pytest.raises(ValueError, match="MODEL_CONFIG_CHANGED"):
        bootstrap(engine, replace(profile, version_label="changed"))


def test_worker_http_same_id_no_network_in_transaction_or_repeated_dispatch(
    http_env, tmp_path, monkeypatch
):
    engine, _, settings, _ = http_env
    profile = load_profile(tmp_path)
    bootstrap(engine, profile)
    source, hid = setup_job(http_env, profile)
    calls, active = [], set()
    event.listen(engine, "begin", lambda c: active.add(c))
    event.listen(engine, "commit", lambda c: active.discard(c))
    event.listen(engine, "rollback", lambda c: active.discard(c))

    def respond(request):
        assert not active
        calls.append(request)
        return httpx.Response(
            200,
            json=dict(
                model="deepseek-flash",
                id="req-1",
                choices=[
                    dict(
                        finish_reason="stop",
                        message=dict(
                            content=json.dumps(
                                dict(
                                    error_category="可能是求和错误",
                                    location_clues="检查输出",
                                    checks="核对读入数量",
                                    learning_advice="先手算样例",
                                )
                            )
                        ),
                    )
                ],
                usage=dict(
                    prompt_tokens=100,
                    completion_tokens=100,
                    prompt_cache_hit_tokens=0,
                    prompt_cache_miss_tokens=100,
                ),
            ),
        )

    monkeypatch.setenv("DeepSeek_API", "fixture-secret")
    worker = build_worker(
        engine, profile, sources=source, http_transport=httpx.MockTransport(respond)
    )
    app = create_app(settings, engine=engine, hint_sources=source, model_profile=profile)
    assert app.state.hint_configuration == worker.configuration == profile.config_id
    assert asyncio.run(worker.run_once())
    assert not asyncio.run(worker.run_once()) and len(calls) == 1
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("ai_hints", hid)["status"] == "READY"
        reservation = repo.get("budget_reservations", hid)
        assert reservation["state"] == "UNCERTAIN" and reservation["actual"] is None
        assert repo.get("budget_accounts", "PROJECT")["uncertain_amount"] == profile.cost_upper_cny


def test_missing_sources_never_loads_key_or_dispatches(http_env, tmp_path, monkeypatch):
    engine = http_env[0]
    profile = load_profile(tmp_path)
    bootstrap(engine, profile)
    monkeypatch.setattr(type(profile), "load_token", lambda _: pytest.fail("must not load key"))
    worker = build_worker(engine, profile)
    assert not asyncio.run(worker.run_once())


def test_raised_deployment_budget_refuses_before_dispatch(http_env, tmp_path, monkeypatch):
    engine = http_env[0]
    profile = load_profile(tmp_path)
    bootstrap(engine, profile)
    source, hid = setup_job(http_env, profile)
    with engine.begin() as connection:
        SqlRepository(connection).change("budget_accounts", "PROJECT", limit_amount=500)
    monkeypatch.setattr(type(profile), "load_token", lambda _: pytest.fail("must not load key"))
    worker = build_worker(engine, profile, sources=source)
    assert not asyncio.run(worker.run_once())
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("ai_hints", hid)["status"] == "FAILED"
        assert repo.get("budget_reservations", hid)["state"] == "RELEASED"


def test_existing_over_budget_liability_refuses_dispatch_without_erasing_history(
    http_env, tmp_path, monkeypatch
):
    engine = http_env[0]
    profile = load_profile(tmp_path)
    bootstrap(engine, profile)
    source, hid = setup_job(http_env, profile)
    with engine.begin() as connection:
        SqlRepository(connection).change("budget_accounts", "PROJECT", settled_amount=21)
    monkeypatch.setattr(type(profile), "load_token", lambda _: pytest.fail("must not load key"))
    assert not asyncio.run(build_worker(engine, profile, sources=source).run_once())
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("budget_accounts", "PROJECT")["settled_amount"] == 21
        assert repo.get("budget_reservations", hid)["state"] == "RELEASED"


def test_missing_key_is_confirmed_local_refusal_releases_reservation(
    http_env, tmp_path, monkeypatch
):
    engine = http_env[0]
    profile = load_profile(tmp_path)
    bootstrap(engine, profile)
    source, hid = setup_job(http_env, profile)

    def missing(_):
        raise ValueError("MODEL_CREDENTIAL_UNAVAILABLE")

    monkeypatch.setattr(type(profile), "load_token", missing)
    assert asyncio.run(build_worker(engine, profile, sources=source).run_once())
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("ai_hints", hid)["status"] == "FAILED"
        assert repo.get("budget_reservations", hid)["state"] == "RELEASED"
