"""
The cognitive complexity limit the CI's complexipy step enforces, checked in
the normal test suite so a function over it fails locally before a push.
The limit is read from that step in the CI workflow, so the two cannot drift
apart.
"""

import re
from pathlib import Path

import complexipy

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = BACKEND_ROOT / "src"
CI_WORKFLOW = BACKEND_ROOT.parent / ".github" / "workflows" / "ci.yml"


def _ci_limit() -> int:
    match = re.search(
        r"complexipy src --max-complexity-allowed (\d+)", CI_WORKFLOW.read_text(encoding="utf-8")
    )
    assert match is not None, f"No complexipy step with a limit found in {CI_WORKFLOW}."
    return int(match.group(1))


def test_no_function_exceeds_the_ci_complexity_limit() -> None:
    limit = _ci_limit()
    offenders = [
        f"{path.relative_to(BACKEND_ROOT)}:{function.line_start} {function.name} "
        f"({function.complexity})"
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
        for function in complexipy.file_complexity(str(path)).functions
        if function.complexity > limit
    ]
    assert not offenders, (
        f"Cognitive complexity above {limit}; split these functions:\n" + "\n".join(offenders)
    )
