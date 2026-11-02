"""Validated deployment configuration; secrets never appear in repr/errors."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.modules.identity.ports import Record


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
            )
        except (KeyError, ValueError):
            raise ValueError("Missing or invalid server configuration.") from None
