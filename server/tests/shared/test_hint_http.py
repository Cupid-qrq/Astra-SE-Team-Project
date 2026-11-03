from decimal import Decimal
from uuid import uuid4

from test_http import http_env as http_env
from test_http import login

from app.main import create_app
from app.modules.learning.application import seed_global_feedback
from app.modules.learning.hint_service import HintService
from app.modules.learning.model_worker import Candidate
from app.modules.learning.policy_rules import HintSource
from app.shared.repository import SqlRepository


def test_formal_hint_http_accept_replay_ready_rating_and_disabled_model(http_env):
    engine, ids, settings, _ = http_env
    submission, config, catalog, version = [str(uuid4()) for _ in range(4)]
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
                body="Review {verdict}.",
                allowed_placeholders=["verdict"],
                schema_version="1",
                author_id=ids["admin"],
                published_at=repo.now(),
                checksum="a" * 64,
            ),
        )
        repo.change("template_catalogs", catalog, active_version_id=version)
        repo.add(
            "model_configs",
            dict(
                config_id=config,
                provider="fixture",
                model_id="fixture",
                version_label="fixture-v1",
                terms_review_ref="test-only",
                price_verified_at=repo.now(),
                input_price=Decimal("1"),
                output_price=Decimal("2"),
                max_input_tokens=1000,
                max_output_tokens=1000,
                enabled=True,
            ),
        )

    class Source:
        def hint_source(self, repo, student_id, submission_id):
            if student_id != ids["student"] or submission_id != submission:
                return None
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
                public_problem="Check a sum.",
                public_samples=[dict(input="1 2", output="3")],
                student_code="print(2)",
                language_key="python3",
                sanitized_diagnostic="",
                verdict="WA",
            )

    source = Source()
    app = create_app(settings, engine=engine, hint_sources=source, hint_configuration=config)
    client = login(app, "student")
    body = dict(submission_id=submission, data_sharing_consent=True, request_key=str(uuid4()))
    accepted = client.post("/api/v1/ai-hints", json=body)
    assert accepted.status_code == 202, accepted.text
    assert accepted.headers["Cache-Control"] == "no-store"
    hid = accepted.json()["hint_id"]
    assert client.post("/api/v1/ai-hints", json=body).json() == accepted.json()
    pending = client.get("/api/v1/ai-hints/" + hid)
    assert pending.status_code == 200 and pending.json()["status"] == "PENDING"
    sections = dict(
        error_category="Possibly formatting",
        location_clues="Check output",
        checks="Compare whitespace",
        learning_advice="Try a boundary value",
    )
    with engine.begin() as connection:
        service = HintService(SqlRepository(connection), source, config)
        permit = service.dispatch(hid)
        assert permit is not None
    with engine.begin() as connection:
        HintService(SqlRepository(connection), source, config).finish(
            hid, permit.lease_epoch, Candidate(sections, None, "SETTLED", Decimal("0.001"))
        )
    replay = client.post("/api/v1/ai-hints", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["sections"] == sections and replay.json()["status"] == "READY"
    view = client.get("/api/v1/ai-hints/" + hid)
    assert view.json() == replay.json()
    assert view.json()["created_at"].endswith("Z")
    assert view.json()["model_version"] == "fixture-v1"
    assert "provider_request_id" not in view.json() and "usage" not in view.json()
    for rating in ("ERROR", "USEFUL"):
        result = client.post(
            "/api/v1/ai-hints/" + hid + "/feedback", json=dict(rating=rating, comment="Check")
        )
        assert result.status_code == 200 and result.json() == dict(rating=rating), result.text
    assert login(app).get("/api/v1/ai-hints/" + hid).json()["sections"] == sections
    disabled = login(create_app(settings, engine=engine, hint_sources=source), "student")
    result = disabled.post("/api/v1/ai-hints", json=body | dict(request_key=str(uuid4())))
    assert result.status_code == 503 and result.json()["code"] == "MODEL_DISABLED", result.text
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert len(repo.rows("ai_hints")) == 1
        assert len(repo.rows("hint_feedback")) == 1

    # Polling must finish an orphaned wait even when the model is now disabled.
    from datetime import timedelta

    retry_body = body | dict(request_key=str(uuid4()))
    queued = client.post("/api/v1/ai-hints", json=retry_body)
    assert queued.status_code == 202, queued.text
    orphan = queued.json()["hint_id"]
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        repo.change("hint_jobs", orphan, deadline_at=repo.now() - timedelta(seconds=1))
    recovered = disabled.get("/api/v1/ai-hints/" + orphan)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["status"] == "FAILED"
    assert recovered.json()["reason_code"] == "QUEUE_TIMEOUT"
    assert recovered.json()["fallback_feedback"]["feedback_version_id"] == feedback
    replay = disabled.post("/api/v1/ai-hints", json=retry_body)
    assert replay.status_code == 200 and replay.json() == recovered.json()
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("hint_jobs", orphan)["state"] == "DONE"
        assert repo.get("budget_reservations", orphan)["state"] == "RELEASED"
