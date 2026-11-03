"""Trusted deployment operation for one explicitly selected immutable template version."""

import re

from app.modules.identity.domain import byte_limit, require, role
from app.modules.identity.ports import Effects, Record, Repository
from app.modules.problems.domain import canonical_hash

from .feedback import ScopedManagement
from .templates import FIELDS, validate_template


def activate_template(
    repo: Repository,
    effects: Effects,
    *,
    actor_id: str,
    template_id: str,
    version_id: str,
    checksum: str,
    reason: str,
) -> Record:
    """Caller owns one transaction containing authorization, pointer, audit and outbox.

    Activation never follows the latest published pointer automatically. Previously
    accepted hints retain their own immutable version, including during rollback.
    """
    repo.guard()
    actor = repo.get("users", actor_id, lock=True)
    require(actor is not None and actor["status"] == "ACTIVE", "FORBIDDEN", "部署身份不可用。", 403)
    assert actor
    role(actor, ("ADMIN", "TEACHER"))
    catalog = ScopedManagement(repo, effects).managed(
        "template_catalogs",
        actor,
        template_id,
        write=True,
    )
    byte_limit(reason, 2000, "启用理由")
    require(
        "\x00" not in reason and 10 <= len(reason.strip()) <= 500,
        "VALIDATION_ERROR",
        "启用理由需要10—500字。",
        422,
    )
    require(
        bool(re.fullmatch(r"[0-9a-f]{64}", checksum)),
        "VALIDATION_ERROR",
        "必须指定已核验的模板校验值。",
        422,
    )
    version = repo.get("template_versions", version_id)
    require(
        version is not None and version["template_id"] == template_id,
        "NOT_FOUND",
        "该目录的模板版本不存在。",
        404,
    )
    assert version
    payload = {key: version[key] for key in FIELDS}
    validate_template(payload)
    require(payload["schema_version"] == "1", "TEMPLATE_UNAVAILABLE", "运行时不支持此结构版本。")
    require(
        checksum == version["checksum"] == canonical_hash(payload),
        "TEMPLATE_CHECKSUM_CHANGED",
        "模板版本校验值不一致，请重新核对。",
    )
    repo.change("template_catalogs", template_id, active_version_id=version_id)
    result = dict(template_id=template_id, version_id=version_id, checksum=checksum)
    effects.record(
        repo,
        actor_id,
        "TEMPLATE_ACTIVATED",
        template_id,
        reason=reason,
        summary=result | dict(previous_version_id=catalog["active_version_id"]),
    )
    return result
