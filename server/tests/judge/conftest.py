from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def snapshot():
    return {
        "profile_id": "20000000-0000-4000-8000-000000000001",
        "languages": [
            {
                "language_key": "cpp17",
                "version": "fixture-cpp",
                "image_digest": "sha256:" + "a" * 64,
                "cpu_time_ms": 2000,
                "wall_time_ms": 5000,
            },
            {
                "language_key": "python3",
                "version": "fixture-python",
                "image_digest": "sha256:" + "b" * 64,
                "cpu_time_ms": 4000,
                "wall_time_ms": 10000,
            },
        ],
        "memory_bytes": 268435456,
        "output_bytes": 1048576,
        "comparison": "ASCII_TOKENS",
        "directory_bytes": 33554432,
        "run_entities": 1,
        "compile_timeout_ms": 20000,
        "compile_memory_bytes": 536870912,
        "compile_entities": 30,
    }


@pytest.fixture
def language_ids():
    # Deliberately not public demo language IDs.
    return {"cpp17": 912, "python3": 733}


@pytest.fixture
def tmp_path():
    workspace = Path(__file__).resolve().parents[3]
    local = workspace / ".local" / "judge-test-tmp"
    local.mkdir(parents=True, exist_ok=True)
    assert local.resolve().is_relative_to(workspace)
    with TemporaryDirectory(prefix="judge-", dir=local) as raw:
        path = Path(raw).resolve()
        assert path.is_relative_to(local.resolve())
        yield path
