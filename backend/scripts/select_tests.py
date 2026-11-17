"""
Prints the backend test files a change can affect, for the local loop. A
changed file under src/modules/<module>/ selects every test that imports that
module or a module that depends on it, so a change to Catalogue also runs the
Workspace and Planning & fulfillment tests that build on it. A changed test
file selects itself, and the whole-codebase guards in GUARDS always run. A
change to the shared kernel, the composition root, the read tier, a conftest
or the dependencies selects the whole suite, since every test reaches them.
CI always runs the whole suite; this only shortens the loop before it.

Usage: poetry run python scripts/select_tests.py [git revision, default HEAD]
       poetry run python scripts/select_tests.py --guards   (only the guards)
Run the result: poetry run pytest $(poetry run python scripts/select_tests.py) -q
"""

import ast
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TESTS = BACKEND / "tests"
# Guards that inspect the whole codebase rather than the code a test imports,
# so a change can break one without selecting it: a new repository without a
# read scenario, a new use case without a race test, a fake that drifts from
# its port. They take seconds. CI's quick-checks job runs them before the
# shards (`--guards`), and the local selection always includes them.
GUARDS = (
    "tests/integration/repository_reads",
    "tests/unit/test_architecture.py",
    "tests/unit/test_complexity.py",
    "tests/unit/test_context_boundaries.py",
    "tests/unit/test_fakes_contract.py",
    "tests/unit/test_race_test_coverage.py",
    "tests/unit/test_request_schema_finite_quantities.py",
    "tests/unit/test_required_guard_collaborators.py",
    "tests/unit/test_state_machine_catalog.py",
    "tests/unit/test_use_case_permission_order.py",
)
EVERYTHING = ("src/shared_kernel/", "src/bootstrap/", "src/read/", "pyproject.toml", "poetry.lock")

sys.path.insert(0, str(BACKEND))
from tests.unit.test_context_boundaries import DEPENDS_ON  # noqa: E402


def changed_files(revision: str) -> list[str]:
    """Files changed against `revision`, staged, unstaged and untracked,
    relative to backend/."""
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "--relative", revision],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return sorted(set(tracked) | set(untracked))


def dependents(modules: set[str]) -> set[str]:
    """The modules and every module that depends on one of them, directly or
    through another module."""
    found = set(modules)
    while True:
        more = {module for module, deps in DEPENDS_ON.items() if deps & found} - found
        if not more:
            return found
        found |= more


def imported_modules(test_file: Path) -> set[str]:
    found: set[str] = set()
    tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            parts = name.split(".")
            if len(parts) > 2 and parts[:2] == ["src", "modules"]:
                found.add(parts[2])
    return found


def select(changed: list[str]) -> list[str]:
    test_files = sorted(p for p in TESTS.rglob("test_*.py") if "pg" not in p.parts)
    if any(f.startswith(EVERYTHING) or f.endswith("conftest.py") for f in changed):
        return ["tests"]
    modules = {
        f.split("/")[2] for f in changed if f.startswith("src/modules/") and f.count("/") > 2
    }
    reached = dependents(modules)
    selected = {f for f in changed if f.startswith("tests/") and (BACKEND / f).is_file()}
    selected |= {
        p.relative_to(BACKEND).as_posix() for p in test_files if imported_modules(p) & reached
    }
    return sorted(selected | set(GUARDS))


def main() -> None:
    if sys.argv[1:] == ["--guards"]:
        print(" ".join(GUARDS))
        return
    revision = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    print(" ".join(select(changed_files(revision))))


if __name__ == "__main__":
    main()
