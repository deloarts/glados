"""
Unit tests for TestBoughtCreate, TestBoughtClaim and
TestBoughtUpdateInPlace. No database, no HTTP. All dependencies replaced
with in-memory fakes.
"""

import pytest

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_order_settings
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file.fakes import FakePartNumberRegistry
from tests.unit.ingest_pdm_file.rig import Rig


class TestBoughtCreate:
    async def test_creates_new_bought_item(self):
        rig = Rig()
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.part_number == "CAD-2001"
        assert item.data_source == DataSource.CAD.value
        assert item.manufacturer_id == 1
        assert item.revision == "3"
        assert item.vault_id == "V1"
        assert item.pdm_file_id == 200
        # One transaction: CreateBoughtItem's own write closure and the PDM
        # link-column patch commit together.
        assert rig.uow.commits == 1

    async def test_creates_even_when_web_creation_is_disabled(self):
        """The admin switch only restricts web users; ingest runs as the
        system user and must still create PDM-numbered rows."""
        rig = Rig(order_settings=make_order_settings(web_creation_allowed=False))
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        assert await rig.bought_item_repo.get_by_id(outcome.item_id) is not None

    async def test_keeps_the_pdm_part_number_when_auto_numbering_is_on(self):
        rig = Rig(order_settings=make_order_settings(part_number_auto=True))
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.part_number == "CAD-2001"
        assert rig.registry.entries.get("CAD-2001") == "bought"

    async def test_exception_after_create_but_before_link_write_rolls_back(self, monkeypatch):
        """Same crash-safety property as the made-item create path:
        CreateBoughtItem's own write and the link-column patch are one
        commit, so a failure patching in the PDM link columns rolls back
        the whole thing rather than leaving a stray committed row without
        its PDM link."""
        rig = Rig()
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))

        def _raise(*_args, **_kwargs):
            raise RuntimeError("snapshot upsert exploded")

        monkeypatch.setattr(rig.snapshot_repo, "upsert_many", _raise)

        with pytest.raises(RuntimeError, match="snapshot upsert exploded"):
            await rig.use_case.execute(payload)

        assert rig.uow.commits == 0
        assert rig.uow.rollbacks >= 1

        # The rollback discarded the item CreateBoughtItem's own write()
        # had already staged, so the same rig, retried with the same
        # payload, must create the item exactly once rather than
        # conflicting with a stray un-rolled-back row.
        monkeypatch.undo()
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "created"
        assert await rig.bought_item_repo.get_by_id(outcome.item_id) is not None
        matching = [i for i in rig.bought_item_repo._items.values() if i.part_number == "CAD-2001"]
        assert len(matching) == 1

    async def test_manufacturer_unresolved_is_a_conflict(self):
        rig = Rig(suppliers=[])  # no supplier #1 exists
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        assert "manufacturer" in outcome.message
        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.sync_state == PdmFileSyncState.CONFLICT.value
        assert snapshot.parked_payload is not None


class TestBoughtClaim:
    async def test_claim_by_gtin(self):
        candidate = make_bought_item(
            1, part_number="OLD-1", data_source=DataSource.WEB, gtin="GTIN-1"
        )
        registry = FakePartNumberRegistry(preclaimed={"OLD-1": "bought"})
        rig = Rig(bought_items=[candidate], registry=registry)
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-1"
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        assert outcome.item_id == 1
        item = await rig.bought_item_repo.get_by_id(1)
        assert item.part_number == "CAD-2001"
        assert item.data_source == DataSource.CAD.value
        assert "Claimed by PDM file V1/200" in outcome.message
        assert "fields overwritten" in outcome.message
        assert "OLD-1" in rig.registry.released
        assert rig.uow.commits == 1  # no sub-use-case call on this path

    async def test_claim_by_manufacturer_and_order_code(self):
        candidate = make_bought_item(
            1,
            part_number="OLD-2",
            data_source=DataSource.WEB,
            gtin=None,
            manufacturer_id=1,
            order_code_1="OC-1",
        )
        registry = FakePartNumberRegistry(preclaimed={"OLD-2": "bought"})
        rig = Rig(bought_items=[candidate], registry=registry)
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        item = await rig.bought_item_repo.get_by_id(1)
        assert item.part_number == "CAD-2001"

    async def test_ambiguous_claim_creates_instead(self):
        # Two WEB rows share the same (manufacturer_id, order_code_1);
        # find_claim_candidate returns None for an ambiguous match, so
        # ingest falls through to a plain create instead of guessing.
        first = make_bought_item(
            1,
            part_number="OLD-3",
            data_source=DataSource.WEB,
            gtin=None,
            manufacturer_id=1,
            order_code_1="OC-1",
        )
        second = make_bought_item(
            2,
            part_number="OLD-4",
            data_source=DataSource.WEB,
            gtin=None,
            manufacturer_id=1,
            order_code_1="OC-1",
        )
        rig = Rig(bought_items=[first, second])
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        assert outcome.item_id not in (1, 2)

    async def test_claim_conflict_on_part_number_clash(self):
        candidate = make_bought_item(
            1, part_number="OLD-5", data_source=DataSource.WEB, gtin="GTIN-5"
        )
        registry = FakePartNumberRegistry(preclaimed={"OLD-5": "bought", "CAD-2001": "made"})
        rig = Rig(bought_items=[candidate], registry=registry)
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-5"
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.part_number == "OLD-5"  # unchanged
        assert stored.pdm_sync_state == PdmSyncState.CONFLICT.value
        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.parked_payload is not None

    async def test_claim_by_gtin_still_works_when_no_part_number_match(self):
        # A row whose part number differs from the payload's, matched
        # instead through the gtin bind key. This proves the new
        # get_by_part_number branch in _ingest_bought does not shadow the
        # existing find_claim_candidate path when no row carries the
        # incoming part number yet.
        candidate = make_bought_item(
            1, part_number="OLD-1", data_source=DataSource.WEB, gtin="GTIN-1"
        )
        registry = FakePartNumberRegistry(preclaimed={"OLD-1": "bought"})
        rig = Rig(bought_items=[candidate], registry=registry)
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-1"
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        item = await rig.bought_item_repo.get_by_id(1)
        assert item.part_number == "CAD-2001"
        assert "Claimed by PDM file V1/200" in outcome.message
        assert "OLD-1" in rig.registry.released

    async def test_claims_cad_sourced_row_without_pdm_link_by_gtin(self):
        # A bought item created through the SolidWorks
        # add-in carries data_source == "CAD" from the moment it is saved,
        # even though it has never been linked to a PDM file
        # (pdm_file_id is None). find_claim_candidate must still offer it
        # as a claim candidate; excluding it would fall through to
        # _bought_create and raise a spurious gtin-duplicate conflict.
        candidate = make_bought_item(
            1, part_number="OLD-6", data_source=DataSource.CAD, gtin="GTIN-6", pdm_file_id=None
        )
        registry = FakePartNumberRegistry(preclaimed={"OLD-6": "bought"})
        rig = Rig(bought_items=[candidate], registry=registry)
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-6"
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        item = await rig.bought_item_repo.get_by_id(1)
        assert item.part_number == "CAD-2001"
        assert item.data_source == DataSource.CAD.value
        assert item.vault_id == "V1"
        assert item.pdm_file_id == 200
        assert "OLD-6" in rig.registry.released

    async def test_claims_unlinked_row_by_part_number_match(self):
        # A live, PDM-unlinked row already carrying the incoming part
        # number is claimed directly, without any gtin/order-code match
        # and without touching the part-number registry: the number is
        # already registered to this row.
        existing = make_bought_item(1, part_number="CAD-2001", data_source=DataSource.WEB)
        registry = FakePartNumberRegistry(preclaimed={"CAD-2001": "bought"})
        rig = Rig(bought_items=[existing], registry=registry)
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.ArticleName"] = "Bolt M8"
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        item = await rig.bought_item_repo.get_by_id(1)
        assert item.part_number == "CAD-2001"
        assert item.article_name == "Bolt M8"
        assert item.data_source == DataSource.CAD.value
        assert item.vault_id == "V1"
        assert item.pdm_file_id == 200
        assert "linked to PDM file V1/200" in outcome.message
        assert registry.released == []  # nothing released: the number never changed

    async def test_conflict_when_part_number_linked_to_another_pdm_file(self):
        existing = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=999,
            pdm_file_version=1,
        )
        rig = Rig(bought_items=[existing])
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        assert "part number linked to another PDM file (id 999)" in outcome.message
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.pdm_sync_state == PdmSyncState.CONFLICT.value
        assert stored.pdm_file_id == 999  # unchanged
        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.parked_payload is not None

    async def test_conflict_when_gtin_matches_a_row_already_linked_to_another_pdm_file(self):
        # The existing row's part number differs from the incoming file's,
        # so the part-number-match branch does not fire and this exercises
        # find_claim_candidate directly: a row already linked to a
        # different PDM file must not be offered as a claim candidate even
        # though its gtin matches, so ingest falls through to a plain
        # create, which then hits the real gtin-duplicate conflict.
        existing = make_bought_item(
            1,
            part_number="OTHER-PN",
            data_source=DataSource.CAD,
            gtin="GTIN-9",
            vault_id="V1",
            pdm_file_id=999,
            pdm_file_version=1,
        )
        rig = Rig(bought_items=[existing])
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-9"
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        assert "GTIN 'GTIN-9' is already in use" in outcome.message
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.pdm_file_id == 999  # unchanged, not claimed


class TestBoughtUpdateInPlace:
    async def test_overwrites_all_mapped_fields(self):
        existing = make_bought_item(
            1,
            part_number="CAD-2001",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=200,
            pdm_file_version=1,
        )
        rig = Rig(bought_items=[existing])
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.ArticleName"] = "Bolt M8"
        payload = make_payload(kind="bought", file_id=200, file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.article_name == "Bolt M8"
        assert stored.part_number == "CAD-2001"  # untouched by design, see report
        assert stored.pdm_file_version == 2
        assert rig.uow.commits == 1


class TestBoughtPartNumberFollowsPdm:
    async def test_in_sync_file_renumbers_its_item(self):
        existing = make_bought_item(
            2,
            part_number="G-26-00009",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=200,
            pdm_file_version=5,
        )
        registry = FakePartNumberRegistry({"G-26-00009": "bought"})
        rig = Rig(bought_items=[existing], registry=registry)

        outcome = await rig.use_case.execute(
            make_payload(
                kind="bought", file_id=200, file_version=5, variables=dict(BOUGHT_VARIABLES)
            )
        )

        assert outcome.action == "updated"
        assert (await rig.bought_item_repo.get_by_id(2)).part_number == "CAD-2001"
        assert registry.entries["CAD-2001"] == "bought"
