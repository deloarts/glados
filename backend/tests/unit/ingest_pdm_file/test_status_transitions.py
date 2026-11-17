"""
Unit tests for TestObsoleteTransition, TestReplacedTransition,
TestSuccessorClearing and TestNewestRevisionSelection. No database, no
HTTP. All dependencies replaced with in-memory fakes.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.domain.events.pdm_events import PdmFileIngested
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import OBSOLETE_STATE_ID
from tests.unit.ingest_pdm_file._helpers import RELEASED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import REPLACED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import UNWATCHED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file.rig import Rig


class TestObsoleteTransition:
    async def test_existing_made_item_flips_to_inactive(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[item])
        payload = make_payload(
            kind="made", state_id=OBSOLETE_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "status"
        assert outcome.item_id == 1
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.status == MadeItemCatalogueStatus.INACTIVE.value
        assert stored.pdm_file_version == 2
        assert stored.pdm_sync_state == PdmSyncState.SYNCED.value
        assert rig.uow.commits == 1
        assert len(rig.bus.published) == 1
        assert isinstance(rig.bus.published[0], PdmFileIngested)
        assert rig.bus.published[0].action == "status"

    async def test_existing_bought_item_flips_to_inactive(self):
        item = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=200,
            pdm_file_version=1,
        )
        rig = Rig(bought_items=[item])
        payload = make_payload(
            kind="bought",
            file_id=200,
            state_id=OBSOLETE_STATE_ID,
            file_version=2,
            variables=dict(BOUGHT_VARIABLES),
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "status"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.status == BoughtItemCatalogueStatus.INACTIVE.value

    async def test_unmatched_state_leaves_existing_item_untouched(self):
        # A state outside every configured list ("state not watched")
        # skips; the linked row is neither status-flipped nor otherwise
        # touched.
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[item])
        payload = make_payload(
            kind="made", state_id=UNWATCHED_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert outcome.message == "state not watched"
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.status == MadeItemCatalogueStatus.ACTIVE.value
        assert stored.pdm_file_version == 1


class TestReplacedTransition:
    """A workflow state in the kind's own replaced list flips the linked
    row's status to `replaced`, the same pure status-only flip as the
    obsolete transition above, and never touches successor_item_id (PDM
    carries no successor reference of its own)."""

    async def test_existing_made_item_flips_to_replaced(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[item])
        payload = make_payload(
            kind="made", state_id=REPLACED_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "status"
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.status == MadeItemCatalogueStatus.REPLACED.value
        assert stored.successor_item_id is None
        assert rig.bus.published[0].action == "status"

    async def test_existing_bought_item_flips_to_replaced(self):
        item = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=200,
            pdm_file_version=1,
        )
        rig = Rig(bought_items=[item])
        payload = make_payload(
            kind="bought",
            file_id=200,
            state_id=REPLACED_STATE_ID,
            file_version=2,
            variables=dict(BOUGHT_VARIABLES),
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "status"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.status == BoughtItemCatalogueStatus.REPLACED.value
        assert stored.successor_item_id is None

    async def test_replaced_state_without_existing_item_is_skipped(self):
        rig = Rig()
        payload = make_payload(
            kind="made", state_id=REPLACED_STATE_ID, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert outcome.message == "replaced state without a matching item"

    async def test_replaced_transition_leaves_an_existing_successor_untouched(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        item.successor_item_id = 42
        rig = Rig(made_items=[item])
        payload = make_payload(
            kind="made", state_id=REPLACED_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        await rig.use_case.execute(payload)
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.status == MadeItemCatalogueStatus.REPLACED.value
        assert stored.successor_item_id == 42


class TestSuccessorClearing:
    """A stale successor_item_id is cleared, with its own changelog
    line, whenever a linked row's status resolves to active or inactive;
    only a replaced target (TestReplacedTransition above) leaves it
    alone."""

    async def test_obsolete_transition_clears_an_existing_successor(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        item.successor_item_id = 42
        rig = Rig(made_items=[item])
        payload = make_payload(
            kind="made", state_id=OBSOLETE_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        await rig.use_case.execute(payload)
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.status == MadeItemCatalogueStatus.INACTIVE.value
        assert stored.successor_item_id is None
        assert any("successor cleared" in line.lower() for line in stored.changes)

    async def test_bought_obsolete_transition_clears_an_existing_successor(self):
        item = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=200,
            pdm_file_version=1,
        )
        item.successor_item_id = 42
        rig = Rig(bought_items=[item])
        payload = make_payload(
            kind="bought",
            file_id=200,
            state_id=OBSOLETE_STATE_ID,
            file_version=2,
            variables=dict(BOUGHT_VARIABLES),
        )
        await rig.use_case.execute(payload)
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.status == BoughtItemCatalogueStatus.INACTIVE.value
        assert stored.successor_item_id is None
        assert any("successor cleared" in line.lower() for line in stored.changes)

    async def test_reactivation_via_in_place_update_clears_an_existing_successor(self):
        # Same revision, same file, no field remap needed to prove the
        # point: a row left `replaced` (or `inactive`) without a revision
        # bump picks up `active` again here too, not just on creation.
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        item.status = MadeItemCatalogueStatus.REPLACED
        item.successor_item_id = 42
        rig = Rig(made_items=[item])
        payload = make_payload(
            kind="made", state_id=RELEASED_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "updated"
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.status == MadeItemCatalogueStatus.ACTIVE.value
        assert stored.successor_item_id is None
        assert any("successor cleared" in line.lower() for line in stored.changes)

    async def test_bought_reactivation_via_claim_clears_an_existing_successor(self):
        item = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=None,
            pdm_file_version=None,
        )
        item.status = BoughtItemCatalogueStatus.REPLACED
        item.successor_item_id = 42
        rig = Rig(bought_items=[item])
        payload = make_payload(
            kind="bought",
            file_id=200,
            state_id=RELEASED_STATE_ID,
            file_version=2,
            variables=dict(BOUGHT_VARIABLES) | {"PDM.PartNumber": "CAD-2001"},
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "claimed"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.status == BoughtItemCatalogueStatus.ACTIVE.value
        assert stored.successor_item_id is None
        assert any("successor cleared" in line.lower() for line in stored.changes)


class TestNewestRevisionSelection:
    """A status-only transition (Rule 6) targets the family's newest
    revision row, ordered by revision.length/revision/created/id
    (revision_scheme.sort_key via get_family_by_pdm_file), never
    insertion order or the lowest id."""

    async def test_obsolete_transition_targets_the_newest_revision(self):
        older = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        newer = make_made_item(
            2,
            part_number="CAD-1001",
            revision="B",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[older, newer])
        payload = make_payload(
            kind="made", state_id=OBSOLETE_STATE_ID, file_version=2, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.item_id == 2
        assert (
            await rig.made_item_repo.get_by_id(2)
        ).status == MadeItemCatalogueStatus.INACTIVE.value
        # The older revision row is untouched.
        assert (
            await rig.made_item_repo.get_by_id(1)
        ).status == MadeItemCatalogueStatus.ACTIVE.value
        assert (await rig.made_item_repo.get_by_id(1)).pdm_file_version == 1
