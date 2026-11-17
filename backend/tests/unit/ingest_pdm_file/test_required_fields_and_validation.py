"""
Unit tests for TestRequiredFields, TestProcessRoleRequired,
TestBoughtRevisionRequirement and TestSnapshotRowStates. No database, no
HTTP. All dependencies replaced with in-memory fakes.
"""

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import MADE_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file.rig import Rig


class TestRequiredFields:
    """Required-field validation (docs/reference/pdm-ingest.md section 7): the
    locked set (part_number, revision and article_name for made; part_number,
    article_name, order_code_1 and manufacturer_id for bought) is enforced
    unconditionally on create/revise/claim; an admin-configured extra field
    or pseudo-rule the same way once selected. In-place updates are never
    checked. A bought item's own revision requirement is a Rule 1 identity
    check rather than part of this locked set; see TestBoughtRevisionRequirement
    below."""

    async def test_made_create_skipped_when_article_name_missing(self):
        rig = Rig()
        variables = dict(MADE_VARIABLES)
        del variables["Glados.ArticleName"]
        payload = make_payload(kind="made", variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: article_name"
        assert await rig.made_item_repo.get_by_id(1) is None
        assert rig.uow.commits == 1  # only the snapshot write, no create attempted

    async def test_bought_create_skipped_when_order_code_1_missing(self):
        rig = Rig()
        variables = dict(BOUGHT_VARIABLES)
        del variables["Glados.OrderCode1"]
        payload = make_payload(kind="bought", variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: order_code_1"

    async def test_made_create_skipped_when_configured_field_missing(self):
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        rig = Rig(pdm_settings=pdm_settings)
        variables = dict(MADE_VARIABLES)
        del variables["Glados.Material"]
        payload = make_payload(kind="made", variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: material"

    async def test_made_create_reports_no_variable_mapped_when_field_unmapped(self):
        made_map = dict(MADE_VAR_MAP)
        made_map["material"] = ""
        pdm_settings = make_pdm_settings(
            made_map=made_map, required_fields={"made": ["material"], "bought": []}
        )
        rig = Rig(pdm_settings=pdm_settings)
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: material (no PDM variable mapped)"

    async def test_made_create_skipped_when_fabrication_step_required_and_missing(self):
        pdm_settings = make_pdm_settings(
            required_fields={"made": ["fabrication_step"], "bought": []}
        )
        rig = Rig(pdm_settings=pdm_settings)
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: fabrication_step"

    async def test_made_revise_skipped_when_configured_field_missing(self):
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        source = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[source], pdm_settings=pdm_settings)
        variables = dict(MADE_VARIABLES)
        variables["PDM.Revision"] = "B"
        del variables["Glados.Material"]
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: material"
        assert (await rig.made_item_repo.get_by_id(1)).revision == "A"  # no new revision created

    async def test_made_update_in_place_never_checks_required_fields(self):
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[item], pdm_settings=pdm_settings)
        variables = dict(MADE_VARIABLES)
        del variables["Glados.Material"]
        variables["Glados.Note"] = "updated note"
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"  # never skipped for a missing required field

    async def test_bought_claim_skipped_when_article_name_missing(self):
        candidate = make_bought_item(
            1, part_number="OLD-1", data_source=DataSource.WEB, gtin="GTIN-1"
        )
        rig = Rig(bought_items=[candidate])
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-1"
        del variables["Glados.ArticleName"]
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "required fields missing: article_name"
        stored = await rig.bought_item_repo.get_by_id(1)
        assert stored.part_number == "OLD-1"  # not claimed


class TestProcessRoleRequired:
    """a Glados.Processes entry with no role is
    malformed, not a signal to assume fabrication; checked at the same
    gate as required fields, before any write."""

    async def test_made_create_skipped_when_a_process_entry_has_no_role(self):
        rig = Rig()
        variables = dict(MADE_VARIABLES)
        variables["Glados.Processes"] = '[{"fabrication_method_id":1,"group_index":0}]'
        payload = make_payload(kind="made", variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "process entry without role"
        assert await rig.made_item_repo.get_by_id(1) is None

    async def test_made_revise_skipped_when_a_process_entry_has_no_role(self):
        source = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[source])
        variables = dict(MADE_VARIABLES)
        variables["PDM.Revision"] = "B"
        variables["Glados.Processes"] = '[{"fabrication_method_id":1,"group_index":0}]'
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "process entry without role"
        assert (await rig.made_item_repo.get_by_id(1)).revision == "A"  # no new revision created

    async def test_made_create_not_flagged_when_processes_unmapped(self):
        # No Glados.Processes variable at all is "unmapped", not a
        # malformed entry, so the check simply does not fire.
        rig = Rig()
        outcome = await rig.use_case.execute(
            make_payload(kind="made", variables=dict(MADE_VARIABLES))
        )

        assert outcome.action == "created"


class TestBoughtRevisionRequirement:
    """revision is data for a bought item, not part of its identity
    (docs/FIELD_OWNERSHIP.md principle 2), so unlike made items its
    requirement is a setting (AdminPdmSettings.required_fields["bought"]),
    checked by Rule 1 alongside part_number; see
    is_revision_required."""

    async def test_skipped_as_identity_missing_when_required_and_absent(self):
        pdm_settings = make_pdm_settings(required_fields={"made": [], "bought": ["revision"]})
        rig = Rig(pdm_settings=pdm_settings)
        variables = dict(BOUGHT_VARIABLES)
        del variables["PDM.Revision"]
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "identity variables missing"
        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.part_number == "CAD-2001"
        assert snapshot.revision is None
        assert await rig.bought_item_repo.get_by_id(1) is None

    async def test_created_with_no_revision_when_not_required_and_absent(self):
        # Default fixture settings: required_fields={"bought": []}, so
        # revision is neither locked nor selected.
        rig = Rig()
        variables = dict(BOUGHT_VARIABLES)
        del variables["PDM.Revision"]
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.revision is None
        snapshot = await rig.snapshot_repo.get_by_file("V1", 200)
        assert snapshot.part_number == "CAD-2001"
        assert snapshot.revision is None

    async def test_created_with_revision_when_present_regardless_of_requirement(self):
        # Whether or not revision is required, a present value is still
        # stored; required only changes what happens when it is blank.
        rig = Rig()
        payload = make_payload(kind="bought", file_id=200, variables=dict(BOUGHT_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert item.revision == "3"


class TestSnapshotRowStates:
    async def test_skip_conflict_and_ingested_states(self):
        rig = Rig()

        skip_payload = make_payload(kind="made", file_id=1, variables={})
        await rig.use_case.execute(skip_payload)
        skipped_snapshot = await rig.snapshot_repo.get_by_file("V1", 1)
        assert skipped_snapshot.sync_state == PdmFileSyncState.SKIPPED.value

        create_payload = make_payload(kind="made", file_id=2, variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(create_payload)
        assert outcome.action == "created"
        ingested_snapshot = await rig.snapshot_repo.get_by_file("V1", 2)
        assert ingested_snapshot.sync_state == PdmFileSyncState.INGESTED.value
        assert ingested_snapshot.last_ingested_version == create_payload.file_version
