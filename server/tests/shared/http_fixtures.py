"""Synthetic public deployment profile; no executable or VM evidence is supplied."""

from uuid import uuid4


def profile():
    return {
        "profile_id": str(uuid4()),
        "languages": [
            {
                "language_key": "cpp17",
                "version": "test-cpp17",
                "image_digest": "sha256:" + "a" * 64,
                "cpu_time_ms": 2000,
                "wall_time_ms": 5000,
            },
            {
                "language_key": "python3",
                "version": "test-python3",
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
