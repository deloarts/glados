"""
The Markdown subset of meeting cards against the shared cases in
tests/fixtures/meeting_markdown_cases.json, which the card editor in the
frontend tests against as well: every input normalises to its expected
text, and the expected text normalises to itself.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from src.modules.workspace.domain.services.meeting_markdown import normalise_card_markdown
from src.modules.workspace.domain.services.meeting_markdown import plain_excerpt
from src.modules.workspace.domain.services.meeting_markdown import referenced_ids

_FIXTURES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "meeting_markdown_cases.json").read_text("utf-8")
)
_USERS = set(_FIXTURES["users"])
_FILES = set(_FIXTURES["files"])


@pytest.mark.parametrize("case", _FIXTURES["cases"], ids=lambda case: case["name"])
def test_meeting_markdown_normalises_each_case(case: dict[str, Any]) -> None:
    result = normalise_card_markdown(case["input"], user_ids=_USERS, file_ids=_FILES)

    assert result.text == case["expected"]
    assert sorted(result.mentioned_user_ids) == case["mentions"]
    assert sorted(result.image_file_ids) == case["images"]


@pytest.mark.parametrize("case", _FIXTURES["cases"], ids=lambda case: case["name"])
def test_meeting_markdown_keeps_the_canonical_form(case: dict[str, Any]) -> None:
    again = normalise_card_markdown(case["expected"], user_ids=_USERS, file_ids=_FILES)

    assert again.text == case["expected"]


def test_meeting_markdown_referenced_ids_name_every_candidate() -> None:
    users, files = referenced_ids("@[A](user:4) ![x](file:7) ![y](https://e.com/a.png)")

    assert users == {4}
    assert files == {7}


def test_meeting_markdown_plain_excerpt_reads_without_markup() -> None:
    bodies = [
        "### Decisions\n\n- Target **9.5 s** stays.",
        "@[Anna Generic](user:2) sends `rev. D`.",
    ]

    assert plain_excerpt(bodies) == "Decisions Target 9.5 s stays. @Anna Generic sends rev. D."
    assert plain_excerpt(["word " * 100], limit=20).endswith("…")
    assert len(plain_excerpt(["word " * 100], limit=20)) == 20
