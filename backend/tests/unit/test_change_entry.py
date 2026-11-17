"""
A ChangeEntry is its changelog line and carries the line's parts: it
round-trips through its record, a plain string is kept whole as text, and
copying or pickling an entry keeps it.
"""

import copy
import pickle
from datetime import UTC
from datetime import datetime

from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.value_objects.change_entry import ChangeEntry

AT = datetime(2026, 10, 26, 7, 30, tzinfo=UTC)


def test_an_entry_is_its_line_and_round_trips_through_its_record() -> None:
    entry = ChangeEntry("Quantity changed.", at=AT, actor="Ada", field="quantity", old="4", new="6")

    assert entry == "2026-10-26 07:30:00, Ada, Quantity changed."
    assert entry.endswith("Quantity changed.")
    record = entry.to_record()
    assert record == {
        "text": "Quantity changed.",
        "at": "2026-10-26 07:30:00",
        "actor": "Ada",
        "field": "quantity",
        "old": "4",
        "new": "6",
    }
    back = ChangeEntry.from_record(record)
    assert (back, back.field, back.old, back.new) == (entry, "quantity", "4", "6")


def test_copying_and_pickling_keep_the_entry() -> None:
    entry = ChangeEntry("Created.", at=AT, actor="Ada")

    assert copy.deepcopy(entry) is entry
    loaded = pickle.loads(pickle.dumps(entry))
    assert (loaded, loaded.actor) == (entry, "Ada")


def test_append_changelog_adds_a_structured_entry_and_keeps_the_old_ones() -> None:
    existing = ["Imported from the old system"]

    updated = append_changelog(existing, "Ada", "Renamed.", field="name", old="A", new="B")

    assert existing == ["Imported from the old system"]
    [kept, added] = updated
    assert kept == "Imported from the old system"
    assert isinstance(added, ChangeEntry)
    assert (added.actor, added.text, added.field, added.old, added.new) == (
        "Ada",
        "Renamed.",
        "name",
        "A",
        "B",
    )
