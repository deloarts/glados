"""
Unit tests for src/modules/platform/application/services/command_changelog.py: the entity's
current values are read for exactly the command's fields, so the changelog
text matches what diff_changes produces from a complete hand-built dict.
"""

from dataclasses import dataclass
from dataclasses import field

from pydantic import BaseModel

from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.command_changelog import entity_values
from src.shared_kernel.domain.services.changelog_service import diff_changes


@dataclass
class _Entity:
    name: str = "Bracket"
    note: str | None = None
    group_ids: list[int] = field(default_factory=lambda: [1])
    internal_only: str = "kept out of the diff"


class _Command(BaseModel):
    note: str | None = None
    name: str = "Bracket"
    group_ids: list[int] = [1]
    propagate: bool | None = None


class TestEntityValues:
    def test_reads_only_the_given_fields_the_entity_has(self):
        values = entity_values(_Entity(), _Command().model_dump())
        assert values == {"note": None, "name": "Bracket", "group_ids": [1]}


class TestDiffCommand:
    def test_no_differences_returns_no_changes_message(self):
        assert diff_command(_Entity(), _Command()) == "No changes."

    def test_matches_diff_changes_on_a_complete_old_dict(self):
        entity = _Entity()
        cmd = _Command(note="new note", name="Bracket v2", group_ids=[1, 2])
        expected = diff_changes(
            {"name": "Bracket", "note": None, "group_ids": [1]}, cmd.model_dump()
        )
        assert diff_command(entity, cmd) == expected
        assert diff_command(entity, cmd) == (
            "Item updated:\n"
            "  • note: None → 'new note'\n"
            "  • name: 'Bracket' → 'Bracket v2'\n"
            "  • group_ids: [1] → [1, 2]"
        )

    def test_a_field_the_entity_lacks_compares_against_none(self):
        result = diff_command(_Entity(), _Command(propagate=True))
        assert result == "Item updated:\n  • propagate: None → True"

    def test_passes_the_heading_through(self):
        result = diff_command(_Entity(), _Command(name="Other"), heading="Lot updated:")
        assert result.startswith("Lot updated:\n")
