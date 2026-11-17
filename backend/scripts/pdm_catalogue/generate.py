"""
Renders operations.json, the hand-finalised catalogue of the SOLIDWORKS PDM
Professional Web API, into src/modules/external_data/adapters/outbound/external/pdm/catalogue.py as
ordinary Python. The output is committed so nothing at import time depends on
the JSON file.

The rendered source is passed through ruff format, then every line ruff check
still reports as too long gets a trailing `# noqa: E501`. Those lines carry
verbatim documentation text or JSON samples that cannot be split without
misrepresenting the help pages. Both ruff steps read the backend's
pyproject.toml, so the output is deterministic for a given ruff version.

Usage (from backend/):
    poetry run python scripts/pdm_catalogue/generate.py          # rewrite catalogue.py
    poetry run python scripts/pdm_catalogue/generate.py --check  # exit 1 on drift
"""

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS_JSON = Path(__file__).resolve().parent / "operations.json"
CATALOGUE_PY = (
    BACKEND_ROOT
    / "src"
    / "modules"
    / "external_data"
    / "adapters"
    / "outbound"
    / "external"
    / "pdm"
    / "catalogue.py"
)
DIFF_LINE_LIMIT = 200

HEADER = '''"""
Declarative catalogue of the SOLIDWORKS PDM Professional Web API 2 (2025),
generated from the official SOLIDWORKS help pages by the tooling in
backend/scripts/pdm_catalogue/, never at runtime. The pages are scraped and
parsed into operations.json, which is finalised by hand and is the source of
truth; generate.py renders it into this file.

113 operations across 17 resource groups; 28 are classified `mutating`
(checkin, upload, delete, changestate, datacard writes, hooks configuration,
user/notification writes, the generic `api/{uri}` POST/PUT/PATCH/DELETE).
`vaultName` path parameters are kept in every spec even though the adapter
always fills them from the connection, so the catalogue stays a faithful mirror
of the documented operations.

Response bodies are intentionally not modelled here; only the operations
Glados actually consumes get typed Pydantic models, in models.py. The admin
API-test console invokes any entry generically through IPdmGateway.invoke and
renders the raw response.

Regenerate with backend/scripts/pdm_catalogue/generate.py after updating
operations.json when SOLIDWORKS ships a new Web API version (see the README
there); do not hand-edit the OPERATIONS tuple below.
"""

from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmParamSpec

'''

FOOTER = (
    ")\n\n"
    "_BY_ID: dict[str, PdmOperationSpec] = {op.id: op for op in OPERATIONS}\n\n\n"
    "def find_operation(op_id: str) -> PdmOperationSpec | None:\n"
    '    """Look up one catalogued operation by its stable id, or None when unknown."""\n'
    "    return _BY_ID.get(op_id)\n"
)


def render_param(param: dict[str, Any]) -> str:
    return (
        "PdmParamSpec("
        f"name={param['name']!r}, "
        f"location={param['in']!r}, "
        f"type={param['type']!r}, "
        f"required={param['required']!r}, "
        f"description={param['description']!r}, "
        ")"
    )


def render_operation(op: dict[str, Any]) -> str:
    params = op["params"]
    if params:
        rows = "".join(f"            {render_param(p)},\n" for p in params)
        params_src = f"(\n{rows}        )"
    else:
        params_src = "()"
    return (
        "    PdmOperationSpec(\n"
        f"        id={op['id']!r},\n"
        f"        method={op['method']!r},\n"
        f"        path={op['path']!r},\n"
        f"        group={op['group']!r},\n"
        f"        description={op['description']!r},\n"
        f"        params={params_src},\n"
        f"        has_body={op['has_body']!r},\n"
        f"        body_example={op['body_example']!r},\n"
        f"        mutating={op['mutating']!r},\n"
        "    ),\n"
    )


def render_raw(operations: list[dict[str, Any]]) -> str:
    """Render the unformatted module source, operations sorted by group and path."""
    ordered = sorted(operations, key=lambda o: (o["group"], o["path"]))
    body = "".join(render_operation(op) for op in ordered)
    return f"{HEADER}OPERATIONS: tuple[PdmOperationSpec, ...] = (\n{body}{FOOTER}"


def run_ruff(args: list[str], source: str) -> subprocess.CompletedProcess[str]:
    """Run ruff on `source` via stdin, as if it were the committed catalogue file."""
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args, "--stdin-filename", str(CATALOGUE_PY), "-"],
        input=source,
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT,
        check=False,
    )


def add_noqa_to_long_lines(source: str) -> str:
    result = run_ruff(["check", "--select", "E501", "--output-format", "json"], source)
    violations = json.loads(result.stdout) if result.stdout.strip() else []
    rows = {v["location"]["row"] for v in violations if v["code"] == "E501"}
    lines = source.split("\n")
    for row in rows:
        if "# noqa" not in lines[row - 1]:
            lines[row - 1] += "  # noqa: E501"
    return "\n".join(lines)


def render_catalogue() -> str:
    operations = json.loads(OPERATIONS_JSON.read_text(encoding="utf-8"))
    formatted = run_ruff(["format"], render_raw(operations))
    if formatted.returncode != 0:
        raise SystemExit(f"ruff format failed:\n{formatted.stderr}")
    return add_noqa_to_long_lines(formatted.stdout)


def drift_report(existing: str, new: str) -> str:
    diff = list(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="a/catalogue.py (committed)",
            tofile="b/catalogue.py (generated)",
        )
    )
    rendered = "".join(diff[:DIFF_LINE_LIMIT])
    if len(diff) > DIFF_LINE_LIMIT:
        rendered += f"... diff truncated, {len(diff) - DIFF_LINE_LIMIT} more lines\n"
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render operations.json into catalogue.py.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed catalogue.py matches operations.json; do not write",
    )
    args = parser.parse_args(argv)

    generated = render_catalogue()
    if args.check:
        existing = CATALOGUE_PY.read_text(encoding="utf-8") if CATALOGUE_PY.exists() else ""
        if existing == generated:
            print(f"{CATALOGUE_PY.relative_to(BACKEND_ROOT)} is up to date")
            return 0
        print(f"{CATALOGUE_PY.relative_to(BACKEND_ROOT)} is out of date:", file=sys.stderr)
        print(drift_report(existing, generated), file=sys.stderr)
        print("Run scripts/pdm_catalogue/generate.py to regenerate it.", file=sys.stderr)
        return 1

    CATALOGUE_PY.write_text(generated, encoding="utf-8")
    print(f"wrote {CATALOGUE_PY.relative_to(BACKEND_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
