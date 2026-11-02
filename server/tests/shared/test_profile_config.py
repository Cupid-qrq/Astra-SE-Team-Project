import json

import pytest
from http_fixtures import profile

from app.shared.config import Settings


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("ASTRA_DATABASE_URL", "postgresql+psycopg://unused/astra_test")
    monkeypatch.setenv("ASTRA_SESSION_SECRET", "test-session-secret-at-least-32-bytes")
    monkeypatch.setenv("ASTRA_ORIGIN", "https://testserver")
    monkeypatch.setenv("ASTRA_READINESS_TOKEN", "test-readiness-secret-at-least-32-bytes")
    monkeypatch.delenv("ASTRA_PROFILES_FILE", raising=False)


def test_profiles_file_is_optional_and_validated(configured, tmp_path, monkeypatch):
    assert Settings.from_env().profiles == ()
    monkeypatch.setenv("ASTRA_PROFILES_FILE", "")
    assert Settings.from_env().profiles == ()
    path = tmp_path / "profiles.json"
    value = profile()
    path.write_text(json.dumps([value]), encoding="utf-8")
    monkeypatch.setenv("ASTRA_PROFILES_FILE", str(path))
    assert Settings.from_env().profiles == (value,)


@pytest.mark.parametrize(
    "raw", ["null", "{}", "[null]", "[{}]", "[NaN]", "not json", "[]" + " " * 1048576]
)
def test_bad_profiles_file_has_safe_error(configured, tmp_path, monkeypatch, raw):
    path = tmp_path / "private-path.json"
    path.write_text(raw, encoding="utf-8")
    monkeypatch.setenv("ASTRA_PROFILES_FILE", str(path))
    with pytest.raises(ValueError) as failure:
        Settings.from_env()
    assert str(failure.value) == "Missing or invalid server configuration."
    assert failure.value.__suppress_context__


def test_missing_file_and_duplicate_profiles_rejected(configured, tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    monkeypatch.setenv("ASTRA_PROFILES_FILE", str(path))
    with pytest.raises(ValueError):
        Settings.from_env()
    value = profile()
    for data in (
        [value, value],
        [value] * 101,
        [value | {"languages": [value["languages"][0]] * 2}],
    ):
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError):
            Settings.from_env()
