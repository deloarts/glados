"""
A file whose part number another ingest writes at the same time: the losing
write fails on a numbering constraint at its commit, which
commit_with_number_retry reports as NumberingConflictError after rolling
back. The ingest decides the file once more and returns an outcome instead
of raising. The Postgres race itself is in
tests/pg/test_pdm_ingest_number_races.py.
"""

from typing import ClassVar

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.platform.domain.exceptions import NumberingConflictError
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file.fakes import FakePartNumberRegistry
from tests.unit.ingest_pdm_file.rig import Rig

_NUMBER = MADE_VARIABLES["PDM.PartNumber"]


class _LosingRegistry(FakePartNumberRegistry):
    """Loses the first `losses` claims as a concurrent ingest would make it
    lose them at the commit. The count lives on the class, because the
    rig's rollback restores every instance attribute."""

    losses: ClassVar[int] = 0

    async def claim(self, part_number: str, kind: str) -> None:
        if type(self).losses > 0:
            type(self).losses -= 1
            raise NumberingConflictError("Could not allocate a unique number after 1 attempts.")
        await super().claim(part_number, kind)


def _rig(losses: int) -> tuple[Rig, type[_LosingRegistry]]:
    registry_type = type("Registry", (_LosingRegistry,), {"losses": losses})
    return Rig(registry=registry_type()), registry_type


async def test_the_losing_file_is_parked_as_a_conflict_with_the_winners_item():
    rig, _ = _rig(losses=1)
    rollback = rig.uow.rollback

    async def rollback_while_the_winner_commits() -> None:
        await rollback()
        if _NUMBER not in rig.registry.entries:
            await rig.made_item_repo.save(
                make_made_item(
                    0,
                    part_number=_NUMBER,
                    data_source=DataSource.CAD,
                    vault_id="V1",
                    pdm_file_id=99,
                    pdm_file_version=5,
                )
            )
            rig.registry.entries[_NUMBER] = "made"
            await rig.uow.commit()

    rig.uow.rollback = rollback_while_the_winner_commits  # type: ignore[method-assign]

    outcome = await rig.use_case.execute(make_payload(kind="made", variables=dict(MADE_VARIABLES)))

    assert outcome.action == "conflict"
    made = [i for i in rig.made_item_repo._items.values() if i.part_number == _NUMBER]
    assert [i.pdm_file_id for i in made] == [99]
    snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
    assert snapshot.sync_state == PdmFileSyncState.CONFLICT.value


async def test_a_second_lost_decision_parks_the_file_instead_of_raising():
    rig, _ = _rig(losses=2)

    outcome = await rig.use_case.execute(make_payload(kind="made", variables=dict(MADE_VARIABLES)))

    assert outcome.action == "conflict"
    assert outcome.message == f"part number {_NUMBER} was written by a concurrent ingest"
    assert list(rig.made_item_repo._items.values()) == []
    snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
    assert snapshot.sync_state == PdmFileSyncState.CONFLICT.value
    assert snapshot.parked_payload is not None


async def test_a_race_the_second_decision_wins_creates_the_item():
    rig, registry_type = _rig(losses=1)

    outcome = await rig.use_case.execute(make_payload(kind="made", variables=dict(MADE_VARIABLES)))

    assert outcome.action == "created"
    assert registry_type.losses == 0
    assert rig.registry.entries == {_NUMBER: "made"}
