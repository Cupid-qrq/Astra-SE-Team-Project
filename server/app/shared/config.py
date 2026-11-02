"""Validated deployment configuration; secrets never appear in repr/errors."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.api.contracts import Contract, text_storage
from app.modules.identity.domain import Fault
from app.modules.identity.ports import Record


def _profiles_from_env() -> tuple[Record, ...]:
    path = os.environ.get("ASTRA_PROFILES_FILE")
    if not path:
        return ()
    with Path(path).open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Invalid profile configuration.")
    values = json.loads(raw.decode("utf-8"))
    if not isinstance(values, list) or len(values) > 100:
        raise ValueError("Invalid profile configuration.")
    contract = Contract.load()
    ids = set()
    for value in values:
        contract.validate({"$ref": "#/components/schemas/Profile"}, value)
        text_storage(value)
        languages = [item["language_key"] for item in value["languages"]]
        if value["profile_id"] in ids or len(set(languages)) != len(languages):
            raise ValueError("Invalid profile configuration.")
        ids.add(value["profile_id"])
    return tuple(values)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    session_secret: bytes = field(repr=False)
    origin: str
    readiness_token: str = field(repr=False)
    profiles: tuple[Record, ...] = ()

    def __post_init__(self) -> None:
        try:
            url = make_url(self.database_url)
            parsed = urlsplit(self.origin)
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.database)
                and len(self.session_secret) >= 32
                and len(self.readiness_token.encode()) >= 32
                and parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
                and all(ord(c) > 32 for c in self.origin)
                and len(self.profiles) <= 100
            )
            _ = parsed.port
        except (ValueError, TypeError, ArgumentError):
            valid = False
        if not valid:
            raise ValueError("Invalid server configuration.") from None

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            return cls(
                os.environ["ASTRA_DATABASE_URL"],
                os.environ["ASTRA_SESSION_SECRET"].encode(),
                os.environ["ASTRA_ORIGIN"],
                os.environ["ASTRA_READINESS_TOKEN"],
                profiles=_profiles_from_env(),
            )
        except (KeyError, ValueError, OSError, Fault, RecursionError):
            raise ValueError("Missing or invalid server configuration.") from None
