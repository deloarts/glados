"""
Unit tests for the pre-write gating rules: TestIdentityAndPattern,
TestKindChangedConflict, TestKindFieldExcludedFromValues, TestState and
TestVersionGuard. No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.domain.events.pdm_events import PdmFileIngested
from src.modules.external_data.domain.events.pdm_events import PdmIngestConflict
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import MADE_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import OBSOLETE_STATE_ID
from tests.unit.ingest_pdm_file._helpers import RELEASED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import UNWATCHED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_made_item_settings
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file.rig import Rig


class TestIdentityAndPattern:
    async def test_missing_part_number_is_skipped(self):
        rig = Rig()
        payload = make_payload(kind="made", variables={"PDM.Revision": "A"})
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert outcome.item_id is None
        assert "identity" in outcome.message
        snapshot = await rig.snapshot_repo.get_by_file(payload.vault_id, payload.file_id)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.SKIPPED.value
        assert snapshot.part_number is None
        assert snapshot.revision == "A"
        assert rig.bus.published == []

    async def test_missing_revision_is_skipped(self):
        rig = Rig()
        payload = make_payload(kind="made", variables={"PDM.PartNumber": "CAD-1"})
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert "identity" in outcome.message
        snapshot = await rig.snapshot_repo.get_by_file(payload.vault_id, payload.file_id)
        assert snapshot is not None
        assert snapshot.part_number == "CAD-1"
        assert snapshot.revision is None

    async def test_skipped_snapshot_records_mapped_article_name(self):
        rig = Rig()
        payload = make_payload(
            kind="made",
            variables={"PDM.PartNumber": "CAD-1", "Glados.ArticleName": "Bracket"},
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        snapshot = await rig.snapshot_repo.get_by_file(payload.vault_id, payload.file_id)
        assert snapshot is not None
        assert snapshot.article_name == "Bracket"

    async def test_part_number_not_matching_pattern_is_skipped(self):
        rig = Rig()
        payload = make_payload(
            kind="made", variables={"PDM.PartNumber": "NOTMATCHING", "PDM.Revision": "A"}
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert "pattern" in outcome.message

    async def test_no_pattern_configured_skips_everything(self):
        rig = Rig(made_item_settings=make_made_item_settings(pdm_part_number_pattern=""))
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert "no external PDM part number pattern configured for made items" in outcome.message
        assert "Numbering settings" in outcome.message


class TestKindChangedConflict:
    async def test_made_payload_conflicts_when_file_already_linked_as_bought(self):
        bought = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(bought_items=[bought])
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        assert outcome.item_id == bought.id
        assert outcome.message == "kind changed, item already linked as bought"
        updated_bought = await rig.bought_item_repo.get_by_id(bought.id)
        assert updated_bought is not None
        assert updated_bought.pdm_sync_state == PdmSyncState.CONFLICT.value
        conflicts = [e for e in rig.bus.published if isinstance(e, PdmIngestConflict)]
        assert len(conflicts) == 1
        assert conflicts[0].kind == "made"
        snapshot = await rig.snapshot_repo.get_by_file(payload.vault_id, payload.file_id)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.CONFLICT.value
        assert snapshot.item_id == bought.id

    async def test_bought_payload_conflicts_when_file_already_linked_as_made(self):
        made = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[made])
        payload = make_payload(kind="bought", variables=dict(BOUGHT_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        assert outcome.item_id == made.id
        assert outcome.message == "kind changed, item already linked as made"
        updated_made = await rig.made_item_repo.get_by_id(made.id)
        assert updated_made is not None
        assert updated_made.pdm_sync_state == PdmSyncState.CONFLICT.value

    async def test_kind_changed_conflict_does_not_ingest(self):
        bought = make_bought_item(
            1, part_number="CAD-2001", data_source=DataSource.CAD, vault_id="V1", pdm_file_id=100
        )
        rig = Rig(bought_items=[bought])
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        await rig.use_case.execute(payload)

        assert await rig.made_item_repo.get_by_id(1) is None
        assert all(not isinstance(e, PdmFileIngested) for e in rig.bus.published)


class TestKindFieldExcludedFromValues:
    """`kind` may be mapped like any other field (docs/FIELD_OWNERSHIP.md,
    principle 1), but it is not a MadeItem/BoughtItem column, so it must
    never reach the create/update commands as a field value."""

    async def test_made_create_ignores_a_mapped_kind_variable(self):
        made_map = dict(MADE_VAR_MAP)
        made_map["kind"] = "Glados.Kind"
        rig = Rig(pdm_settings=make_pdm_settings(made_map=made_map))
        variables = dict(MADE_VARIABLES)
        variables["Glados.Kind"] = "made"
        payload = make_payload(kind="made", variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"


class TestState:
    async def test_unwatched_state_is_skipped(self):
        rig = Rig()
        payload = make_payload(
            kind="made", state_id=UNWATCHED_STATE_ID, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert "state" in outcome.message

    async def test_unwatched_state_is_reported_before_missing_identity(self):
        """A file still being worked on usually has no PDM revision yet; its
        skip must name the state, not an identity problem."""
        rig = Rig()
        payload = make_payload(
            kind="made", state_id=UNWATCHED_STATE_ID, variables={"PDM.PartNumber": "CAD-1001"}
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert outcome.message == "state not watched"
        snapshot = await rig.snapshot_repo.get_by_file(payload.vault_id, payload.file_id)
        assert snapshot.part_number == "CAD-1001"

    async def test_obsolete_state_without_existing_item_is_skipped(self):
        rig = Rig()
        payload = make_payload(
            kind="made", state_id=OBSOLETE_STATE_ID, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert "obsolete" in outcome.message

    async def test_state_watched_for_bought_but_not_for_made_skips_the_made_file(self):
        # Made and bought each check the payload's state against their own
        # pair of lists: a state released for bought is not automatically
        # released (or even watched) for made.
        pdm_settings = make_pdm_settings(
            made_released_state_ids=[],
            made_obsolete_state_ids=[],
            bought_released_state_ids=[RELEASED_STATE_ID],
            bought_obsolete_state_ids=[OBSOLETE_STATE_ID],
        )
        rig = Rig(pdm_settings=pdm_settings)
        payload = make_payload(
            kind="made", state_id=RELEASED_STATE_ID, variables=dict(MADE_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert outcome.message == "state not watched"

    async def test_state_watched_for_made_but_not_for_bought_skips_the_bought_file(self):
        pdm_settings = make_pdm_settings(
            made_released_state_ids=[RELEASED_STATE_ID],
            made_obsolete_state_ids=[OBSOLETE_STATE_ID],
            bought_released_state_ids=[],
            bought_obsolete_state_ids=[],
        )
        rig = Rig(pdm_settings=pdm_settings)
        payload = make_payload(
            kind="bought", state_id=RELEASED_STATE_ID, variables=dict(BOUGHT_VARIABLES)
        )
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert outcome.message == "state not watched"


class TestVersionGuard:
    async def test_equal_version_is_skipped(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=5,
        )
        rig = Rig(made_items=[item])
        payload = make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"
        assert "already at version" in outcome.message
        assert rig.uow.commits == 1  # snapshot-only write, still one transaction

    async def test_lower_version_is_skipped(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=9,
        )
        rig = Rig(made_items=[item])
        payload = make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "skipped"

    async def test_equal_version_keeps_the_link_and_resyncs_the_item(self):
        """A forced poll re-ingests a linked file at its unchanged version,
        for example after it reappeared from missing. The snapshot must stay
        linked and read ingested, and the item must read synced again."""
        item = self._linked_made_item(pdm_file_version=5)
        item.pdm_sync_state = PdmSyncState.MISSING
        rig = Rig(made_items=[item])
        payload = make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.item_id is None  # nothing written, so no write-back
        snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
        assert snapshot.item_id == 1
        assert snapshot.sync_state == PdmFileSyncState.INGESTED.value
        assert snapshot.last_error is None
        assert (await rig.made_item_repo.get_by_id(1)).pdm_sync_state == PdmSyncState.SYNCED.value

    async def test_lower_version_keeps_the_link_but_stays_skipped(self):
        rig = Rig(made_items=[self._linked_made_item(pdm_file_version=9)])
        payload = make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))

        await rig.use_case.execute(payload)

        snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
        assert snapshot.item_id == 1
        assert snapshot.sync_state == PdmFileSyncState.SKIPPED.value
        assert snapshot.last_error == "already at version 9"

    async def test_equal_version_with_a_new_state_still_flips_the_status(self):
        """A workflow transition need not create a new file version, so an
        obsolete state at the stored version must still reach rule 7."""
        rig = Rig(made_items=[self._linked_made_item(pdm_file_version=5)])
        payload = make_payload(
            kind="made",
            file_version=5,
            state_id=OBSOLETE_STATE_ID,
            variables=dict(MADE_VARIABLES),
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "status"
        assert (await rig.made_item_repo.get_by_id(1)).status == "inactive"

    async def test_bought_equal_version_keeps_the_link(self):
        item = make_bought_item(
            2,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=200,
            pdm_file_version=5,
        )
        rig = Rig(bought_items=[item])
        payload = make_payload(
            kind="bought", file_id=200, file_version=5, variables=dict(BOUGHT_VARIABLES)
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.item_id == 2
        assert snapshot.sync_state == PdmFileSyncState.INGESTED.value

    @staticmethod
    def _linked_made_item(*, pdm_file_version: int):
        return make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=pdm_file_version,
        )

    async def test_higher_version_proceeds(self):
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
        payload = make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)
        assert outcome.action in ("updated", "skipped")
        assert outcome.message != "already at version 1"
