from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from test_http import http_env as http_env

from app.modules.identity.domain import Fault
from app.modules.learning.model_activation import activate_template
from app.modules.learning.templates import TemplateManagement
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


def published(http_env, *, global_scope=False):
    engine, ids, _, _ = http_env
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        effects = TransactionalEffects(repo, str(uuid4()))
        manager = TemplateManagement(repo, effects)
        actor = repo.get("users", ids["admin" if global_scope else "teacher"])
        body = dict(
            scope="GLOBAL" if global_scope else "COURSE",
            draft=dict(body="核对 {verdict}", allowed_placeholders=["verdict"], schema_version="1"),
        )
        if not global_scope:
            body["course_id"] = ids["course"]
        tid = manager.create_catalog(actor, body)["template_id"]
        version = manager.publish(
            actor, tid, dict(expected_revision=1, reason="已核对教学提示及安全边界")
        )
        return tid, version


def call(engine, actor, tid, version, **changes):
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        return activate_template(
            repo,
            TransactionalEffects(repo, str(uuid4())),
            actor_id=actor,
            template_id=tid,
            version_id=version["version_id"],
            checksum=version["checksum"],
            reason="已完成部署核验并明确启用该版本",
            **changes,
        )


@pytest.mark.parametrize("global_scope", [False, True])
def test_explicit_activation_checks_persisted_actor_and_audits_atomic_transition(
    http_env, global_scope
):
    engine, ids, _, _ = http_env
    tid, version = published(http_env, global_scope=global_scope)
    actor = ids["admin" if global_scope else "teacher"]
    result = call(engine, actor, tid, version)
    assert result == dict(template_id=tid, **version)
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("template_catalogs", tid)["active_version_id"] == version["version_id"]
        assert len(repo.rows("audit_events", action="TEMPLATE_ACTIVATED", actor_id=actor)) == 1
        assert len(repo.rows("outbox_events", event_type="TEMPLATE_ACTIVATED")) == 1
        assert (
            repo.get("template_versions", version["version_id"])["checksum"] == version["checksum"]
        )


@pytest.mark.parametrize(
    "kind",
    [
        "student",
        "cross_course",
        "wrong_version",
        "stale_checksum",
        "archived",
        "disabled",
        "reason",
    ],
)
def test_activation_failures_leave_active_pointer_and_effects_unchanged(http_env, kind):
    engine, ids, _, _ = http_env
    tid, version = published(http_env)
    actor = ids["teacher"]
    arguments = dict(
        actor_id=actor,
        template_id=tid,
        version_id=version["version_id"],
        checksum=version["checksum"],
        reason="已完成部署核验并明确启用该版本",
    )
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        if kind == "student":
            arguments["actor_id"] = ids["student"]
        elif kind == "cross_course":
            other = str(uuid4())
            repo.add(
                "users", repo.get("users", actor) | dict(user_id=other, login_name="anotherteacher")
            )
            arguments["actor_id"] = other
        elif kind == "wrong_version":
            _, wrong = published(http_env, global_scope=True)
            arguments["version_id"] = wrong["version_id"]
            arguments["checksum"] = wrong["checksum"]
        elif kind == "stale_checksum":
            arguments["checksum"] = "0" * 64
        elif kind == "archived":
            repo.change("courses", ids["course"], status="ARCHIVED", archived_at=repo.now())
        elif kind == "disabled":
            repo.change("users", actor, status="DISABLED")
        elif kind == "reason":
            arguments["reason"] = "short"
    with pytest.raises(Fault):
        with engine.begin() as connection:
            repo = SqlRepository(connection)
            activate_template(repo, TransactionalEffects(repo, str(uuid4())), **arguments)
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("template_catalogs", tid)["active_version_id"] is None
        assert not repo.rows("audit_events", action="TEMPLATE_ACTIVATED")
        assert not repo.rows("outbox_events", event_type="TEMPLATE_ACTIVATED")


@pytest.mark.parametrize("table", ["audit_events", "outbox_events"])
def test_activation_effect_failure_rolls_back_pointer_and_both_effects(http_env, table):
    engine, ids, _, _ = http_env
    tid, version = published(http_env)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"ALTER TABLE {table} ADD CONSTRAINT reject_activation CHECK(false) NOT VALID"
        )
    with pytest.raises(IntegrityError):
        call(engine, ids["teacher"], tid, version)
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        assert repo.get("template_catalogs", tid)["active_version_id"] is None
        assert not repo.rows("audit_events", action="TEMPLATE_ACTIVATED")
        assert not repo.rows("outbox_events", event_type="TEMPLATE_ACTIVATED")


def test_publication_never_switches_explicitly_activated_version(http_env):
    engine, ids, _, _ = http_env
    tid, first = published(http_env)
    call(engine, ids["teacher"], tid, first)
    with engine.begin() as connection:
        repo = SqlRepository(connection)
        manager = TemplateManagement(repo, TransactionalEffects(repo, str(uuid4())))
        actor = repo.get("users", ids["teacher"])
        second = manager.publish(
            actor, tid, dict(expected_revision=2, reason="另一个版本发布但尚未部署启用")
        )
        assert second["version_id"] != first["version_id"]
        catalog = repo.get("template_catalogs", tid)
        assert catalog["published_version_id"] == second["version_id"]
        assert catalog["active_version_id"] == first["version_id"]
