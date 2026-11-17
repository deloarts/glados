"""
Unit tests for the EPLAN Data Portal link PDM ingest takes from a bought
file's datacard: create, claim and in-place update apply edp_part_id under
the shadow rule of docs/FIELD_OWNERSHIP.md principle 7 and request the
picture of a new link. No database, no HTTP.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file.rig import Rig

_LINKED_AT = datetime(2026, 5, 1, tzinfo=UTC)


def _settings():
    return make_pdm_settings(bought_map={**BOUGHT_VAR_MAP, "edp_part_id": "Glados.EdpPartId"})


def _variables(edp_part_id: str) -> dict[str, str]:
    return {**BOUGHT_VARIABLES, "Glados.EdpPartId": edp_part_id}


def _linked_row(*, edp_part_id: int | None, pdm_edp_part_id: int | None):
    """A CAD row already linked to file 200, at file version 1."""
    item = make_bought_item(
        1,
        part_number="CAD-2001",
        data_source=DataSource.CAD,
        vault_id="V1",
        pdm_file_id=200,
        pdm_file_version=1,
    )
    return replace(
        item,
        edp_part_id=edp_part_id,
        edp_synced_at=_LINKED_AT if edp_part_id is not None else None,
        pdm_edp_part_id=pdm_edp_part_id,
    )


def _picture_requests(rig: Rig) -> list[int]:
    return [e.item_id for e in rig.bus.published if isinstance(e, BoughtItemEdpPictureRequested)]


class TestCreate:
    async def test_links_the_new_item_and_requests_its_picture(self):
        rig = Rig(pdm_settings=_settings())
        payload = make_payload(kind="bought", file_id=200, variables=_variables("4711"))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.edp_part_id == 4711
        assert item.pdm_edp_part_id == 4711
        assert item.edp_synced_at is not None
        assert any("EPLAN Data Portal part #4711" in str(c) for c in item.changes)
        assert _picture_requests(rig) == [item.id]

    async def test_blank_value_creates_an_unlinked_item(self):
        rig = Rig(pdm_settings=_settings())
        payload = make_payload(kind="bought", file_id=200, variables=_variables(""))

        outcome = await rig.use_case.execute(payload)

        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.edp_part_id is None
        assert item.pdm_edp_part_id is None
        assert _picture_requests(rig) == []

    async def test_malformed_value_reads_as_no_part(self):
        rig = Rig(pdm_settings=_settings())
        payload = make_payload(kind="bought", file_id=200, variables=_variables("not-a-number"))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.edp_part_id is None


class TestUpdateInPlace:
    async def test_an_unchanged_file_keeps_a_link_made_in_the_web(self):
        existing = _linked_row(edp_part_id=5, pdm_edp_part_id=7)
        rig = Rig(bought_items=[existing], pdm_settings=_settings())
        payload = make_payload(
            kind="bought", file_id=200, file_version=2, variables=_variables("7")
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id == 5
        assert stored.edp_synced_at == _LINKED_AT
        assert _picture_requests(rig) == []

    async def test_a_changed_file_value_relinks(self):
        existing = _linked_row(edp_part_id=5, pdm_edp_part_id=7)
        rig = Rig(bought_items=[existing], pdm_settings=_settings())
        payload = make_payload(
            kind="bought", file_id=200, file_version=2, variables=_variables("9")
        )

        await rig.use_case.execute(payload)

        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id == 9
        assert stored.pdm_edp_part_id == 9
        assert any("EPLAN Data Portal part #9" in str(c) for c in stored.changes)
        assert _picture_requests(rig) == [1]

    async def test_an_emptied_file_value_unlinks(self):
        existing = _linked_row(edp_part_id=7, pdm_edp_part_id=7)
        rig = Rig(bought_items=[existing], pdm_settings=_settings())
        payload = make_payload(kind="bought", file_id=200, file_version=2, variables=_variables(""))

        await rig.use_case.execute(payload)

        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id is None
        assert stored.edp_synced_at is None
        assert stored.pdm_edp_part_id is None
        assert any("Unlinked from EPLAN Data Portal part #7" in str(c) for c in stored.changes)
        # The worker removes the portal picture of an unlinked item.
        assert _picture_requests(rig) == [1]

    async def test_a_file_value_equal_to_the_web_link_only_records_the_shadow(self):
        existing = _linked_row(edp_part_id=7, pdm_edp_part_id=None)
        rig = Rig(bought_items=[existing], pdm_settings=_settings())
        payload = make_payload(
            kind="bought", file_id=200, file_version=2, variables=_variables("7")
        )

        await rig.use_case.execute(payload)

        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id == 7
        assert stored.pdm_edp_part_id == 7
        assert stored.edp_synced_at == _LINKED_AT
        assert not any("Data Portal" in str(c) for c in stored.changes)
        assert _picture_requests(rig) == []

    async def test_an_unmapped_field_leaves_the_link_alone(self):
        existing = _linked_row(edp_part_id=5, pdm_edp_part_id=7)
        rig = Rig(bought_items=[existing], pdm_settings=make_pdm_settings())
        payload = make_payload(
            kind="bought", file_id=200, file_version=2, variables=_variables("9")
        )

        await rig.use_case.execute(payload)

        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id == 5
        assert stored.pdm_edp_part_id == 7


class TestClaim:
    async def test_a_blank_file_value_keeps_the_web_rows_link(self):
        candidate = replace(
            make_bought_item(1, part_number=None, data_source=DataSource.WEB),
            edp_part_id=5,
            edp_synced_at=_LINKED_AT,
        )
        rig = Rig(bought_items=[candidate], pdm_settings=_settings())
        payload = make_payload(kind="bought", file_id=200, variables=_variables(""))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id == 5
        assert _picture_requests(rig) == []

    async def test_a_file_value_links_the_claimed_row(self):
        candidate = make_bought_item(1, part_number=None, data_source=DataSource.WEB)
        rig = Rig(bought_items=[candidate], pdm_settings=_settings())
        payload = make_payload(kind="bought", file_id=200, variables=_variables("4711"))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.edp_part_id == 4711
        assert stored.pdm_edp_part_id == 4711
        assert _picture_requests(rig) == [1]
