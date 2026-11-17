"""
The main ingest paths under the settings a production vault runs with: the
integration enabled, web creation off and automatic part numbers on for both
catalogues. The other modules default to permissive settings, which is how
ingest once broke under these without a single failing test.
"""

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import OBSOLETE_STATE_ID
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_made_item_settings
from tests.unit.ingest_pdm_file._helpers import make_order_settings
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file.rig import Rig


def _production_rig(**kwargs) -> Rig:
    return Rig(
        made_item_settings=make_made_item_settings(
            web_creation_allowed=False, part_number_auto=True
        ),
        order_settings=make_order_settings(web_creation_allowed=False, part_number_auto=True),
        **kwargs,
    )


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


def _linked_bought_item(*, pdm_file_version: int):
    return make_bought_item(
        2,
        part_number="CAD-2001",
        data_source=DataSource.CAD,
        vault_id="V1",
        pdm_file_id=200,
        pdm_file_version=pdm_file_version,
    )


class TestMadeItemsUnderProductionSettings:
    async def test_create_keeps_the_pdm_part_number(self):
        rig = _production_rig()

        outcome = await rig.use_case.execute(
            make_payload(kind="made", variables=dict(MADE_VARIABLES))
        )

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.part_number == "CAD-1001"
        assert rig.registry.entries == {"CAD-1001": "made"}

    async def test_revision_keeps_the_family_part_number(self):
        rig = _production_rig(made_items=[_linked_made_item(pdm_file_version=1)])
        variables = dict(MADE_VARIABLES)
        variables["PDM.Revision"] = "B"

        outcome = await rig.use_case.execute(
            make_payload(kind="made", file_version=2, variables=variables)
        )

        assert outcome.action == "revised"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert (item.part_number, item.revision) == ("CAD-1001", "B")

    async def test_in_place_update_applies(self):
        rig = _production_rig(made_items=[_linked_made_item(pdm_file_version=1)])

        outcome = await rig.use_case.execute(
            make_payload(kind="made", file_version=2, variables=dict(MADE_VARIABLES))
        )

        assert outcome.action in ("updated", "skipped")
        assert (await rig.made_item_repo.get_by_id(1)).pdm_file_version == 2

    async def test_obsolete_state_flips_the_status(self):
        rig = _production_rig(made_items=[_linked_made_item(pdm_file_version=1)])

        outcome = await rig.use_case.execute(
            make_payload(
                kind="made",
                file_version=2,
                state_id=OBSOLETE_STATE_ID,
                variables=dict(MADE_VARIABLES),
            )
        )

        assert outcome.action == "status"
        item = await rig.made_item_repo.get_by_id(1)
        assert item.status == MadeItemCatalogueStatus.INACTIVE.value

    async def test_reingest_at_the_same_version_stays_linked(self):
        rig = _production_rig(made_items=[_linked_made_item(pdm_file_version=5)])

        await rig.use_case.execute(
            make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        )

        snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
        assert snapshot.item_id == 1
        assert snapshot.sync_state == PdmFileSyncState.INGESTED.value


class TestBoughtItemsUnderProductionSettings:
    async def test_create_keeps_the_pdm_part_number(self):
        rig = _production_rig()

        outcome = await rig.use_case.execute(
            make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))
        )

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.part_number == "CAD-2001"
        assert rig.registry.entries == {"CAD-2001": "bought"}

    async def test_in_place_update_applies(self):
        rig = _production_rig(bought_items=[_linked_bought_item(pdm_file_version=1)])

        outcome = await rig.use_case.execute(
            make_payload(
                kind="bought", file_id=200, file_version=2, variables=dict(BOUGHT_VARIABLES)
            )
        )

        assert outcome.action == "updated"
        assert (await rig.bought_item_repo.get_by_id(2)).pdm_file_version == 2

    async def test_reingest_at_the_same_version_stays_linked(self):
        rig = _production_rig(bought_items=[_linked_bought_item(pdm_file_version=5)])

        await rig.use_case.execute(
            make_payload(
                kind="bought", file_id=200, file_version=5, variables=dict(BOUGHT_VARIABLES)
            )
        )

        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.item_id == 2
        assert snapshot.sync_state == PdmFileSyncState.INGESTED.value
