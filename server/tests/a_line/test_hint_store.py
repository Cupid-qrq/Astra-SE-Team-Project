from decimal import Decimal
from uuid import uuid4

import pytest
from app.modules.identity.domain import Fault
from app.modules.learning.application import seed_global_feedback
from app.modules.learning.hint_service import HintService
from app.modules.learning.model_worker import Candidate
from app.modules.learning.policy_rules import HintSource
from astra_a.storage import SqlRepository
from test_assignments import make_assignment


def setup_hint(env):
    _, course, problem, _, _, _ = make_assignment(env)
    student = env.users["student_a"]
    submission, model, catalog, version = (str(uuid4()) for _ in range(4))

    class Source:
        def hint_source(self, repo, student_id, submission_id):
            return HintSource(submission, student, course, problem, "FINISHED", "WA", fixed)

        def hint_context(self, repo, source):
            return dict(
                public_problem="题目",
                public_samples=[{"input": "1", "output": "2"}],
                student_code="print(1)",
                language_key="python3",
                sanitized_diagnostic="",
                verdict="WA",
            )

    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        fixed = seed_global_feedback(repo, env.users["admin_a"])["WA"]
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
                body="提示",
                allowed_placeholders=[],
                schema_version="1",
                author_id=env.users["admin_a"],
                published_at=repo.now(),
                checksum="a" * 64,
            ),
        )
        repo.change("template_catalogs", catalog, active_version_id=version)
        repo.add(
            "model_configs",
            dict(
                config_id=model,
                version_label="offline-test",
                provider="fixture",
                model_id="fixture",
                terms_review_ref="fixture",
                price_verified_at=repo.now(),
                input_price=Decimal("1"),
                output_price=Decimal("2"),
                max_input_tokens=1000,
                max_output_tokens=1000,
                enabled=True,
            ),
        )
    return (
        Source(),
        model,
        dict(user_id=student, role="STUDENT"),
        dict(submission_id=submission, data_sharing_consent=True, request_key=str(uuid4())),
    )


def test_reserve_replay_dispatch_and_unknown_cost(env):
    source, model, actor, body = setup_hint(env)
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        status, accepted = service.create(actor, body)
        hid = accepted["hint_id"]
        assert status == 202 and service.create(actor, body) == (202, accepted)
        with pytest.raises(Fault) as busy:
            service.create(actor, body | {"request_key": str(uuid4())})
        assert busy.value.status == 429
        permit = service.dispatch(hid)
        assert permit and permit.context["student_code"] == "print(1)"
        assert service.dispatch(hid) is None
        service.finish(hid, permit.lease_epoch, Candidate(None, "MODEL_TIMEOUT", "UNCERTAIN", None))
        service.finish(hid, permit.lease_epoch, Candidate(None, "MODEL_TIMEOUT", "UNCERTAIN", None))
        assert service.create(actor, body)[0] == 200
        assert service.read(actor, hid)["status"] == "FAILED"
        assert repo.rows("quota_ledger")[0]["reserved"] == 0
        assert all(a["uncertain_amount"] == Decimal("0.003") for a in repo.rows("budget_accounts"))
        assert service.reconcile(hid, Decimal("0.001"))
        assert not service.reconcile(hid, Decimal("0.001"))
        assert all(
            a["settled_amount"] == Decimal("0.001") and not a["uncertain_amount"]
            for a in repo.rows("budget_accounts")
        )


def test_ready_rate_and_historical_redaction_preserve_charges(env):
    source, model, actor, body = setup_hint(env)
    sections = dict(
        error_category="可能是输出格式",
        location_clues="查看最后一次输出",
        checks="检查换行",
        learning_advice="重跑样例",
    )
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        _, accepted = service.create(actor, body)
        hid = accepted["hint_id"]
        permit = service.dispatch(hid)
        assert not service.finish(
            hid, permit.lease_epoch + 1, Candidate(sections, None, "SETTLED", Decimal("0.001"))
        )
        assert service.finish(
            hid, permit.lease_epoch, Candidate(sections, None, "SETTLED", Decimal("0.001"))
        )
        assert service.read(actor, hid)["sections"] == sections
        for rating in ("ERROR", "USEFUL"):
            assert service.rate(actor, hid, dict(rating=rating)) == dict(rating=rating)
        assert len(repo.rows("hint_feedback")) == 1
        a = repo.rows("assignments")[0]
        repo.change(
            "assignments", a["assignment_id"], published_at=env.clock(), open_at=env.clock()
        )
        assert service.read(actor, hid)["sections"] is None
        assert service.read(actor, hid)["fallback_feedback"]["title"] == "答案错误"
        with pytest.raises(Fault):
            service.rate(actor, hid, dict(rating="ERROR"))
        assert repo.rows("quota_ledger")[0]["ready"] == 1


def test_concurrent_replay_and_rollover_budget_denial_rollback(env):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta

    source, model, actor, body = setup_hint(env)

    def submit(data):
        with env.engine.begin() as conn:
            return HintService(SqlRepository(conn, env.clock), source, model).create(actor, data)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [body, body]))
    assert results[0] == results[1]
    old = results[0][1]["hint_id"]
    env.clock.advance(timedelta(days=1))
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        service.expire()
        assert service.read(actor, old)["reason_code"] == "QUEUE_TIMEOUT"
        assert repo.rows("quota_ledger")[0]["reserved"] == 0
        repo.change("budget_accounts", "PROJECT", settled_amount=Decimal("499.999"))
    with pytest.raises(Fault) as denied:
        submit(body | {"request_key": str(uuid4())})
    assert denied.value.code == "MODEL_BUDGET_EXHAUSTED"
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        assert len(repo.rows("ai_hints")) == 1 and len(repo.rows("budget_accounts")) == 2


def test_waiting_open_blocks_dispatch_and_dispatch_open_blocks_ready(env):
    source, model, actor, body = setup_hint(env)
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        assignment = repo.rows("assignments")[0]["assignment_id"]
        _, response = service.create(actor, body)
        first = response["hint_id"]
        repo.change("assignments", assignment, published_at=env.clock(), open_at=env.clock())
        assert not service.dispatch(first)
        assert repo.get("ai_hints", first)["status"] == "BLOCKED"
        assert repo.get("budget_reservations", first)["state"] == "RELEASED"
        repo.change("assignments", assignment, ai_policy="GUIDED")
        second = service.create(actor, body | {"request_key": str(uuid4())})[1]["hint_id"]
        permit = service.dispatch(second)
        repo.change("assignments", assignment, ai_policy="DISABLED")
        service.finish(
            second,
            permit.lease_epoch,
            Candidate(dict(checks="private"), None, "SETTLED", Decimal("0.002")),
        )
        assert repo.get("ai_hints", second)["status"] == "BLOCKED"
        assert repo.get("ai_hints", second)["sections"] is None
        assert repo.get("budget_reservations", second)["actual"] == Decimal("0.002")


def test_worker_closes_transaction_before_transport_and_rechecks_at_writeback(env):
    import asyncio
    import json
    from contextlib import contextmanager

    from app.modules.learning.hint_runner import run_one
    from app.modules.learning.model_worker import ModelReply

    source, model, actor, body = setup_hint(env)
    live = 0

    @contextmanager
    def transaction():
        nonlocal live
        with env.engine.begin() as conn:
            live += 1
            try:
                yield HintService(SqlRepository(conn, env.clock), source, model)
            finally:
                live -= 1

    with transaction() as service:
        _, accepted = service.create(actor, body)

    class Local:
        async def generate(self, context, model):
            assert live == 0
            return ModelReply(
                json.dumps(
                    dict(error_category="a", location_clues="b", checks="c", learning_advice="d")
                ),
                Decimal("0.001"),
            )

    assert asyncio.run(run_one(transaction, Local(), lambda sections: True))
    assert not asyncio.run(run_one(transaction, Local(), lambda sections: True))
    with transaction() as service:
        assert service.read(actor, accepted["hint_id"])["status"] == "READY"


def test_two_execution_slots_ten_waiters_and_overdue_lease(env):
    from dataclasses import replace
    from datetime import timedelta

    source, model, actor, body = setup_hint(env)
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        original = source.hint_source(repo, actor["user_id"], body["submission_id"])

        class Multi:
            def hint_source(self, repo, student, submission):
                return replace(original, student_id=student, submission_id=submission)

            def hint_context(self, repo, source_info):
                return source.hint_context(repo, source_info)

        service = HintService(repo, Multi(), model)
        baseline = repo.get("users", actor["user_id"])
        members = []
        for i in range(13):
            uid = str(uuid4())
            repo.add("users", baseline | dict(user_id=uid, login_name="student" + str(i)))
            repo.add(
                "course_members",
                repo.rows("course_members", user_id=actor["user_id"])[0] | dict(user_id=uid),
            )
            members.append(actor | dict(user_id=uid))
        jobs = []
        for person in members[:10]:
            jobs.append(service.create(person, body | dict(request_key=str(uuid4())))[1]["hint_id"])
        with pytest.raises(Fault) as full:
            service.create(members[10], body | dict(request_key=str(uuid4())))
        assert full.value.code == "HINT_QUEUE_FULL"
        running = [service.dispatch(hid) for hid in jobs[:2]]
        assert all(running) and not service.dispatch(jobs[2])
        for person in members[10:12]:
            service.create(person, body | dict(request_key=str(uuid4())))
        env.clock.advance(timedelta(seconds=10))
        service.expire()
        assert len(repo.rows("hint_jobs", state="RUNNING")) == 2
        assert len(repo.rows("budget_reservations", state="RELEASED")) == 10
        env.clock.advance(timedelta(seconds=10))
        service.expire()
        assert len(repo.rows("budget_reservations", state="UNCERTAIN")) == 2
        assert service.finish(
            jobs[0], running[0].lease_epoch, Candidate(None, "LATE", "SETTLED", Decimal("0.002"))
        )
        assert repo.get("ai_hints", jobs[0])["status"] == "FAILED"


def test_daily_twentieth_ready_reservation_and_next_day(env):
    from datetime import timedelta

    source, model, actor, body = setup_hint(env)
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        hid = service.create(actor, body)[1]["hint_id"]
        permit = service.dispatch(hid)
        service.finish(hid, permit.lease_epoch, Candidate(None, "MODEL_TIMEOUT", "UNCERTAIN", None))
        quota = repo.rows("quota_ledger")[0]
        key = actor["user_id"], quota["accepted_date"]
        repo.change("quota_ledger", key, ready=19)
        second = service.create(actor, body | dict(request_key=str(uuid4())))[1]["hint_id"]
        permit = service.dispatch(second)
        service.finish(
            second,
            permit.lease_epoch,
            Candidate(
                dict(error_category="a", location_clues="b", checks="c", learning_advice="d"),
                None,
                "SETTLED",
                Decimal("0.001"),
            ),
        )
    with pytest.raises(Fault) as denied:
        with env.engine.begin() as conn:
            HintService(SqlRepository(conn, env.clock), source, model).create(
                actor, body | dict(request_key=str(uuid4()))
            )
    assert denied.value.code == "HINT_DAILY_LIMIT"
    env.clock.advance(timedelta(days=1))
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        assert service.create(actor, body | dict(request_key=str(uuid4())))[0] == 202
        assert len(repo.rows("quota_ledger")) == 2


def test_late_authoritative_receipt_settles_once_without_reopening_hint(env):
    from datetime import timedelta

    source, model, actor, body = setup_hint(env)
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        service = HintService(repo, source, model)
        hid = service.create(actor, body)[1]["hint_id"]
        permit = service.dispatch(hid)
        env.clock.advance(timedelta(seconds=21))
        service.expire()
        old = repo.get("ai_hints", hid)
        candidate = Candidate(
            dict(error_category="a", location_clues="b", checks="c", learning_advice="d"),
            None,
            "SETTLED",
            Decimal("0.001"),
            usage={"prompt_tokens": 10, "completion_tokens": 2},
            provider_request_id="late-receipt",
        )
        assert not service.finish(hid, permit.lease_epoch + 1, candidate)
        assert service.finish(hid, permit.lease_epoch, candidate)
        current = repo.get("ai_hints", hid)
        assert current["status"] == old["status"] == "FAILED"
        assert current["reason_code"] == old["reason_code"] == "MODEL_TIMEOUT"
        assert current["sections"] is None
        assert current["usage"] == candidate.usage
        assert current["provider_request_id"] == "late-receipt"
        assert repo.get("budget_reservations", hid)["actual"] == Decimal("0.001")
        for account in repo.rows("budget_accounts"):
            assert account["settled_amount"] == Decimal("0.001")
            assert account["uncertain_amount"] == account["reserved_amount"] == 0
        quota = repo.rows("quota_ledger")[0]
        assert quota["ready"] == quota["reserved"] == 0
        assert not service.finish(hid, permit.lease_epoch, candidate)
        assert not service.reconcile(hid, Decimal("0.001"))
