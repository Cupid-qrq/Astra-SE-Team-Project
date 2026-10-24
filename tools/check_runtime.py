"""Run the product checks when runtime files exist; share this gate locally and in CI."""

from pathlib import Path, PurePosixPath
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = ("apps", "server", "tests", "infra")
IGNORED = {"node_modules", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
           "dist", "build", "test-results", "test-results-production", "test-results-integration", "playwright-report", "coverage", ".local"}


def source_files(directory):
    """Prune generated directories before walking; never inspect vendored docs."""
    for current, directories, files in os.walk(directory):
        directories[:] = sorted(name for name in directories if name not in IGNORED)
        for name in sorted(files):
            yield Path(current) / name


def requires_runtime(paths):
    for name in paths:
        path = PurePosixPath(str(name).replace("\\", "/"))
        if (path.parts and path.parts[0] in RUNTIME_DIRS
                and path.name != "README.md" and not IGNORED.intersection(path.parts)):
            return True
    return False


def runtime_files():
    return (p.relative_to(ROOT).as_posix() for name in RUNTIME_DIRS
            for p in source_files(ROOT / name))


def run_runtime_check(script):
    if not script.is_file():
        print("Runtime files require tools/check_all.ps1; missing entry.", file=sys.stderr)
        return 1
    try:
        return subprocess.run(["pwsh", "-NoProfile", "-File", str(script.resolve())],
                              cwd=ROOT, check=False).returncode
    except OSError as error:
        print(f"Unable to run product checks: {error}", file=sys.stderr)
        return 1


def main():
    if not requires_runtime(runtime_files()):
        print("Planning-only checkout: no product runtime checks apply.")
        return 0
    return run_runtime_check(ROOT / "tools/check_all.ps1")


if __name__ == "__main__":
    sys.exit(main())
