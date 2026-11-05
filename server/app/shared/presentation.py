"""Optional deployment display names. Never change authoritative stored records."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class PresentationNames:
    def __init__(self, names: Mapping[str, str]) -> None:
        if len(names) > 1000 or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not key.strip()
            or not value.strip()
            or len(key) > 500
            or len(value) > 100
            or any(ord(c) < 32 for c in key + value)
            for key, value in names.items()
        ):
            raise ValueError("INVALID_PRESENTATION_NAMES")
        self.names = dict(names)

    @classmethod
    def from_file(cls, path: str | None) -> "PresentationNames":
        if not path:
            return cls({})
        source = Path(path)
        if source.stat().st_size > 256 * 1024:
            raise ValueError("INVALID_PRESENTATION_NAMES")
        value = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("INVALID_PRESENTATION_NAMES")
        return cls(value)

    def project(self, value: Any) -> Any:
        if not self.names:
            return value
        if isinstance(value, list):
            return [self.project(item) for item in value]
        if isinstance(value, dict):
            return {
                key: self.names.get(item, item)
                if key in ("title", "course_title", "assignment_title", "problem_title")
                and isinstance(item, str)
                else self.project(item)
                if isinstance(item, (dict, list))
                else item
                for key, item in value.items()
            }
        return value
