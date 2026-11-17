"""
Parses the operation pages written by scrape.py (`api-*.txt`) into a draft
operations JSON file: one entry per documented operation with its method,
path, resource group, description, parameters, a request body sample and a
`mutating` classification.

The output is a draft, not the source of truth. The help pages are irregular,
so the committed operations.json was corrected by hand after parsing. When
SOLIDWORKS ships a new Web API version, diff this draft against
operations.json and carry over the real changes by hand.

Stdlib only. Usage:
    python scripts/pdm_catalogue/parse_pages.py /tmp/pdmdocs /tmp/operations.draft.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

DESCRIPTION_LIMIT = 300

# POST/PUT endpoints that only read (searches, lookups, login, tree builds),
# so they are not classified as mutating despite their HTTP method.
_READ_ONLY_PATH = re.compile(
    r"/(search|searchvariables|info|infofrompath|files/info|folders/info|state/transitions"
    r"|HistoryComments|DynamicNotificationUsers|authenticate|buildtree)(\b|$)"
)
_SIGNATURE = re.compile(r"^\s*(Get|Post|Put|Patch|Delete) \| (api/[^|]+?) \|", re.M)
_GROUP = re.compile(r"> (.+?) Resource Group")
_DESCRIPTION = re.compile(r"Description\n(.*?)\n\s*Parameters\n", re.S)
_PARAMETERS = re.compile(r"\tParameters\n(.*?)(?=\nRequest  \(|\nResponse  \(|\Z)", re.S)
_PARAM_ROW = re.compile(r"\n([A-Za-z][A-Za-z0-9_ ]*) \| (.*?) \| ([^|\n]*?) \| ", re.S)
_REQUEST_SECTION = re.compile(
    r"Request  \([^)]*\)\n(.*?)(?=\nRequest  \(|\nResponse  \(|\n\s*Remarks|\Z)", re.S
)


def parse_description(text: str) -> str:
    match = _DESCRIPTION.search(text)
    if not match:
        return ""
    description = " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())
    # Many descriptions start by repeating the route ("GET: api/..."); drop that.
    return re.sub(r"^(GET|POST|PUT|DELETE|PATCH): \S+\s*", "", description)


def param_location(name: str, description: str, path: str) -> str:
    if f"?{name}=" in path or f"&{name}=" in path:
        return "query"
    if "{" + name + "}" in path:
        return "path"
    if "Body" in description:
        return "body"
    if "URI" in description:
        return "path"
    return "unknown"


def parse_params(text: str, path: str) -> list[dict[str, Any]]:
    """Read the parameters table, skipping response members and the header row."""
    match = _PARAMETERS.search(text)
    if not match:
        return []
    params = []
    for name, raw_description, data_type in _PARAM_ROW.findall("\n" + match.group(1)):
        description = " ".join(raw_description.split())
        is_response = "(Response" in description
        is_model_member = (
            "Member of" in description and "(URI" not in description and "(Body" not in description
        )
        if is_response or is_model_member:
            continue
        location = param_location(name, description, path)
        required = bool(re.search(r"required", description, re.I)) or location == "path"
        if name.strip() == "Name" and data_type.strip() == "Data Type":
            continue
        params.append(
            {
                "name": name.strip(),
                "in": location,
                "type": data_type.strip(),
                "required": required,
                "description": description,
            }
        )
    return params


def parse_body_example(text: str) -> str | None:
    """Return the first request sample that looks like JSON, if any."""
    for section in _REQUEST_SECTION.finditer(text):
        sample = re.search(r"Sample Data\n(.*)", section.group(1), re.S)
        if sample and sample.group(1).lstrip()[:1] in '{["':
            return sample.group(1).strip()
    return None


def parse_page(page: Path) -> dict[str, Any] | None:
    """Parse one operation page, or return None when it has no operation signature."""
    text = page.read_text(encoding="utf-8")
    signature = _SIGNATURE.search(text)
    if not signature:
        return None
    method = signature.group(1).upper()
    path = signature.group(2).strip()
    group_match = _GROUP.search(text)
    body_example = parse_body_example(text)
    has_body = body_example is not None or (
        method in ("POST", "PUT", "PATCH") and "Request  (application/json" in text
    )
    mutating = method in ("POST", "PUT", "PATCH", "DELETE") and not _READ_ONLY_PATH.search(path)
    return {
        "id": re.sub(r"[^a-z0-9]+", "_", f"{method} {path}".lower()).strip("_"),
        "method": method,
        "path": path,
        "group": group_match.group(1).strip() if group_match else "?",
        "description": parse_description(text)[:DESCRIPTION_LIMIT],
        "params": parse_params(text, path),
        "has_body": has_body,
        "body_example": body_example,
        "mutating": mutating,
        "source": page.name,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse scraped PDM help pages into JSON.")
    parser.add_argument("pages_dir", type=Path, help="directory written by scrape.py")
    parser.add_argument("output", type=Path, help="draft operations JSON file to write")
    args = parser.parse_args(argv)

    operations = []
    for page in sorted(args.pages_dir.glob("api-*.txt")):
        operation = parse_page(page)
        if operation is None:
            print(f"SKIP {page}")
            continue
        operations.append(operation)

    args.output.write_text(json.dumps(operations, indent=1), encoding="utf-8")
    mutating = sum(op["mutating"] for op in operations)
    unknown = sum(any(p["in"] == "unknown" for p in op["params"]) for op in operations)
    print(f"{len(operations)} ops; {mutating} mutating; {unknown} with unknown param loc")
    print(Counter(op["group"] for op in operations))
    return 0


if __name__ == "__main__":
    sys.exit(main())
