"""
Numbers drawn from number_counter_table: the first draw of a prefix starts
after the highest number stored under it by length and then by value, later
draws count on the counter, families count separately, an outgrown padding
never jams, and the prefix matches literally. The stored numbers here live
in the part number registry, a table with nothing but a number column.
"""

from datetime import date

from src.modules.catalogue.adapters.outbound.persistence.models.part_number_registry_model import (
    PartNumberRegistryOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.number_counters import (
    highest_stored_sequence,
)

_COLUMN = PartNumberRegistryOrmModel.part_number
_TODAY = date(2026, 10, 25)


async def _store(db, *numbers: str) -> None:
    db.add_all(
        PartNumberRegistryOrmModel(part_number=number, kind="made", created=_TODAY)
        for number in numbers
    )
    await db.flush()


async def _draw(db, template: str, family: NumberFamily = NumberFamily.LOT) -> str:
    return await draw_number(db, family, template, column=_COLUMN, today=_TODAY)


async def test_the_first_draw_starts_after_the_highest_stored_number(db) -> None:
    await _store(db, "L2026998", "L20261000", "L2026999")

    assert await _draw(db, "L{year}{seq:03d}") == "L20261001"


async def test_later_draws_count_on_the_counter(db) -> None:
    await _store(db, "L20265")

    first = await _draw(db, "L{year}{seq:03d}")
    # A number stored afterwards is not read again; the counter decides.
    await _store(db, "L2026900")
    second = await _draw(db, "L{year}{seq:03d}")

    assert (first, second) == ("L2026006", "L2026007")


async def test_an_outgrown_padding_never_jams(db) -> None:
    await _store(db, *(f"P-{n}" for n in range(1, 10)))

    drawn = [await _draw(db, "P-{seq}") for _ in range(3)]

    assert drawn == ["P-10", "P-11", "P-12"]


async def test_two_families_count_the_same_prefix_separately(db) -> None:
    assert await _draw(db, "X-{seq:02d}", NumberFamily.ORDER) == "X-01"
    assert await _draw(db, "X-{seq:02d}", NumberFamily.LOT) == "X-01"
    assert await _draw(db, "X-{seq:02d}", NumberFamily.ORDER) == "X-02"


async def test_a_prefix_with_like_wildcards_matches_literally(db) -> None:
    await _store(db, "LA_7", "L%_9", "L__3")

    assert await highest_stored_sequence(db, _COLUMN, "L__") == 3
    assert await highest_stored_sequence(db, _COLUMN, "L%_") == 9


async def test_stored_numbers_whose_rest_is_not_all_digits_are_ignored(db) -> None:
    await _store(db, "Q-12", "Q-12A", "Q-ZZZZZZ")

    assert await highest_stored_sequence(db, _COLUMN, "Q-") == 12
    assert await highest_stored_sequence(db, _COLUMN, "NONE-") == 0
