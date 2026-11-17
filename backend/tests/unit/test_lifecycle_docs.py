"""
docs/LIFECYCLES.md is generated from the state machine catalogue by
scripts/export_lifecycle_docs.py. This fails when a lifecycle changed and
the page was not regenerated, so the page never describes a lifecycle the
code no longer has.
"""

from scripts.export_lifecycle_docs import DOC_PATH
from scripts.export_lifecycle_docs import render


def test_the_lifecycle_page_matches_the_code() -> None:
    assert DOC_PATH.read_text(encoding="utf-8") == render(), (
        "docs/LIFECYCLES.md is stale; run `poetry run python scripts/export_lifecycle_docs.py` "
        "from backend/ and commit the result"
    )


def test_every_lifecycle_has_a_diagram() -> None:
    page = render()
    assert page.count("```mermaid") == page.count("\n## ")
