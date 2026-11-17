"""
Unit tests for ValidatePdmPayload, the pre-release validation dry run
(docs/reference/pdm-ingest.md section 8). Reuses the fakes and settings
builders from tests/unit/ingest_pdm_file/: both suites exercise the same
rules against the same in-memory catalogue, and ValidatePdmPayload itself
shares its field-resolution helpers with IngestPdmFile
(application.services.pdm_field_resolution), so keeping one set of fakes
in sync is enough for both.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.application.dto.pdm_dto import ValidatePdmPayloadCommand
from src.modules.external_data.application.use_cases.pdm.validate_pdm_payload import (
    ValidatePdmPayload,
)
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import MADE_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import make_article_group
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_made_item_settings
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file._helpers import make_supplier
from tests.unit.ingest_pdm_file.fakes import FakeAdminSettingsRepository
from tests.unit.ingest_pdm_file.fakes import FakeArticleGroupRepository
from tests.unit.ingest_pdm_file.fakes import FakeBoughtItemRepository
from tests.unit.ingest_pdm_file.fakes import FakeMadeItemRepository
from tests.unit.ingest_pdm_file.fakes import FakePartNumberRegistry
from tests.unit.ingest_pdm_file.fakes import FakePdmFileSnapshotRepository
from tests.unit.ingest_pdm_file.fakes import FakeSourceItemRepository
from tests.unit.ingest_pdm_file.fakes import FakeSupplierRepository
from tests.unit.made_item.fakes import FakeCustomerRepository


def make_snapshot(
    *, vault_id: str = "V1", file_id: int, path: str, kind: str | None = "bought"
) -> PdmFileSnapshot:
    now = datetime.now(UTC)
    return PdmFileSnapshot(
        id=0,
        vault_id=vault_id,
        file_id=file_id,
        kind=kind,
        name=path.rsplit("\\", 1)[-1],
        path=path,
        parent_folder_id=1,
        version=1,
        state_id=10,
        state="Released",
        modified_at=None,
        first_seen_at=now,
        last_seen_at=now,
        last_ingested_version=None,
        sync_state=PdmFileSyncState.PENDING,
        last_error=None,
        part_number=None,
        revision=None,
        item_id=None,
        parked_payload=None,
    )


# ── Test rig ─────────────────────────────────────────────────────────


class Rig:
    def __init__(
        self,
        *,
        made_items=None,
        bought_items=None,
        article_groups=None,
        source_items=None,
        suppliers=None,
        pdm_settings=None,
        made_item_settings=None,
        order_settings=None,
        registry=None,
    ) -> None:
        self.made_item_repo = FakeMadeItemRepository(made_items)
        self.bought_item_repo = FakeBoughtItemRepository(bought_items)
        self.article_group_repo = FakeArticleGroupRepository(article_groups)
        self.source_item_repo = FakeSourceItemRepository(source_items)
        self.supplier_repo = FakeSupplierRepository(
            suppliers if suppliers is not None else [make_supplier(id=1)]
        )
        self.admin_settings_repo = FakeAdminSettingsRepository(
            made_items=made_item_settings, orders=order_settings, pdm=pdm_settings
        )
        self.registry = registry or FakePartNumberRegistry()
        self.snapshot_repo = FakePdmFileSnapshotRepository()

        self.use_case = ValidatePdmPayload(
            self.made_item_repo,
            self.bought_item_repo,
            self.article_group_repo,
            self.source_item_repo,
            self.supplier_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            pdm_file_snapshot_repo=self.snapshot_repo,
            customer_repo=FakeCustomerRepository(),
        )


async def make_rig(*, snapshots: list[PdmFileSnapshot], **kwargs) -> Rig:
    """A Rig whose snapshot table is seeded, which needs the async fake."""
    rig = Rig(**kwargs)
    await rig.snapshot_repo.upsert_many(snapshots)
    return rig


def make_cmd(
    *,
    kind: str | None = "made",
    variables: dict[str, str] | None = None,
    file_name: str | None = None,
    vault_id: str | None = None,
    file_id: int | None = None,
    file_path: str | None = None,
) -> ValidatePdmPayloadCommand:
    return ValidatePdmPayloadCommand(
        kind=kind,
        variables=variables if variables is not None else {},
        file_name=file_name,
        vault_id=vault_id,
        file_id=file_id,
        file_path=file_path,
    )


MADE_VARIABLES = {
    "PDM.PartNumber": "CAD-1001",
    "PDM.Revision": "A",
    "Glados.ArticleName": "Bracket",
}

BOUGHT_VARIABLES = {
    "PDM.PartNumber": "CAD-2001",
    "PDM.Revision": "3",
    "Glados.ArticleName": "Bolt M6",
    "Glados.OrderCode1": "OC-1",
    "Glados.ManufacturerId": "1",
}


# ── Integration switch: PDM not enabled ─────────────────────────────


class TestNotEnabled:
    async def test_disabled_raises(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        rig.admin_settings_repo._pdm.enabled = False
        with pytest.raises(PdmNotEnabledError):
            await rig.use_case.execute(make_cmd(variables=dict(MADE_VARIABLES)))

    async def test_unconfigured_raises(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        rig.admin_settings_repo._pdm.password = None
        with pytest.raises(PdmNotEnabledError):
            await rig.use_case.execute(make_cmd(variables=dict(MADE_VARIABLES)))


# ── Kind resolution ──────────────────────────────────────────────────


class TestKindResolution:
    async def test_kind_not_set_when_neither_given_nor_mapped(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(make_cmd(kind=None, variables={}))
        assert result.ok is False
        assert result.reasons == ["kind not set"]
        assert result.kind is None
        assert result.would == "unknown"

    async def test_kind_resolved_from_glados_kind_variable(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.Kind"] = "made"
        result = await rig.use_case.execute(make_cmd(kind=None, variables=variables))
        assert result.kind == "made"
        assert result.would == "created"

    async def test_garbage_kind_variable_leaves_kind_unresolved(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.Kind"] = "nonsense"
        result = await rig.use_case.execute(make_cmd(kind=None, variables=variables))
        assert result.ok is False
        assert result.reasons == ["kind not set"]


# ── Rule 1: identity variables missing ──────────────────────────────


class TestIdentity:
    async def test_missing_part_number_and_revision_are_pending_not_a_reason(self):
        # part_number/revision are PDM-owned, so a missing one is not counted as
        # "identity variables missing" and does not force `would` to "unknown": it
        # lands in `pending_pdm` instead, and `would` predicts as if PDM had already
        # assigned it (see TestPendingPdm). `ok` is still false here only because
        # this rig's empty variables also leave article_name (engineer-owned,
        # locked) missing.
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(make_cmd(kind="made", variables={}))
        assert result.ok is False
        assert "identity variables missing" not in result.reasons
        assert result.reasons == ["required fields missing: article_name"]
        assert result.pending_pdm == ["part_number", "revision"]
        assert result.would == "created"

    async def test_part_number_present_revision_missing_is_pending_not_a_reason(self):
        # Revision missing, like part_number missing above, is `pending_pdm`, and
        # `would` predicts "created" (no family exists for this part number).
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = {"PDM.PartNumber": "CAD-1001"}
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert "identity variables missing" not in result.reasons
        assert result.reasons == ["required fields missing: article_name"]
        assert result.pending_pdm == ["revision"]
        assert result.would == "created"
        assert result.part_number == "CAD-1001"
        assert result.revision is None


# ── Rule 2: external pattern ─────────────────────────────────────────


class TestPattern:
    async def test_no_pattern_configured(self):
        rig = Rig(
            pdm_settings=make_pdm_settings(),
            made_item_settings=make_made_item_settings(pdm_part_number_pattern=""),
        )
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert any("no external PDM part number pattern configured" in r for r in result.reasons)
        assert result.ok is False

    async def test_pattern_mismatch(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["PDM.PartNumber"] = "NOT-MATCHING"
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert "part number does not match the configured PDM pattern" in result.reasons
        assert result.ok is False

    async def test_pattern_match_bought(self):
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP))
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert "part number does not match the configured PDM pattern" not in result.reasons


# ── Kind changed (linked row under the OTHER kind) ──────────────────


class TestKindChanged:
    async def test_no_check_without_file_identity(self):
        """The PAT surface with no vault_id/file_id/file_path has nothing
        to resolve an identity from, so this check is simply skipped
        rather than raising or reporting anything."""
        existing = make_bought_item(id=1, part_number="CAD-1001", vault_id="V1", pdm_file_id=100)
        rig = Rig(pdm_settings=make_pdm_settings(), bought_items=[existing])
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables=dict(MADE_VARIABLES), vault_id=None, file_id=None)
        )
        assert not any("kind changed" in r for r in result.reasons)
        assert result.file_identity == "unresolved"

    async def test_flagged_when_file_identity_given(self):
        existing = make_bought_item(id=1, part_number="CAD-9999", vault_id="V1", pdm_file_id=100)
        rig = Rig(pdm_settings=make_pdm_settings(), bought_items=[existing])
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables=dict(MADE_VARIABLES), vault_id="V1", file_id=100)
        )
        assert "kind changed, item already linked as bought" in result.reasons
        assert result.ok is False
        assert result.file_identity == "not_applicable"

    async def test_flagged_when_file_identity_resolved_from_path(self):
        # the PAT surface has no vault_id/file_id of its
        # own but can supply file_path, resolved to the same file identity
        # via the snapshot table. The other-kind-link check then runs
        # exactly as it would with a directly-given identity.
        existing = make_bought_item(id=1, part_number="CAD-9999", vault_id="V1", pdm_file_id=100)
        snapshot = make_snapshot(
            vault_id="V1", file_id=100, path="\\Engineering\\Glados\\CAD-9999.sldprt"
        )
        rig = await make_rig(
            pdm_settings=make_pdm_settings(vault_id="V1"),
            bought_items=[existing],
            snapshots=[snapshot],
        )
        result = await rig.use_case.execute(
            make_cmd(
                kind="made",
                variables=dict(MADE_VARIABLES),
                file_path="C:\\DEMO-VAULT\\Engineering\\Glados\\CAD-9999.sldprt",
            )
        )
        assert "kind changed, item already linked as bought" in result.reasons
        assert result.ok is False
        assert result.file_identity == "resolved"

    async def test_unresolved_when_file_path_matches_no_snapshot(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(
            make_cmd(
                kind="made",
                variables=dict(MADE_VARIABLES),
                file_path="C:\\DEMO-VAULT\\Engineering\\Glados\\unknown.sldprt",
            )
        )
        assert result.file_identity == "unresolved"

    async def test_resolution_is_case_and_separator_insensitive(self):
        snapshot = make_snapshot(
            vault_id="V1", file_id=100, path="\\Engineering\\Glados\\CAD-9999.SLDPRT"
        )
        rig = await make_rig(pdm_settings=make_pdm_settings(vault_id="V1"), snapshots=[snapshot])
        result = await rig.use_case.execute(
            make_cmd(
                kind="made",
                variables=dict(MADE_VARIABLES),
                file_path="c:/demo-vault/engineering/glados/cad-9999.sldprt",
            )
        )
        assert result.file_identity == "resolved"


# ── Registry clash ───────────────────────────────────────────────────


class TestRegistryClash:
    async def test_part_number_already_registered_to_other_kind(self):
        registry = FakePartNumberRegistry(preclaimed={"CAD-1001": "bought"})
        rig = Rig(pdm_settings=make_pdm_settings(), registry=registry)
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert "part number is already registered to bought" in result.reasons
        assert result.ok is False

    async def test_no_clash_when_registered_to_the_same_kind(self):
        registry = FakePartNumberRegistry(preclaimed={"CAD-1001": "made"})
        rig = Rig(pdm_settings=make_pdm_settings(), registry=registry)
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert not any("already registered" in r for r in result.reasons)


# ── Extension rule ───────────────────────────────────────────────────


class TestExtensionRule:
    async def test_wrong_extension_for_kind(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables=dict(MADE_VARIABLES), file_name="part.sldasm")
        )
        assert "sldasm files are not made items" in result.reasons
        assert result.ok is False

    async def test_admitted_extension_passes(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables=dict(MADE_VARIABLES), file_name="part.sldprt")
        )
        assert not any("files are not" in r for r in result.reasons)

    async def test_no_file_name_skips_the_check(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables=dict(MADE_VARIABLES), file_name=None)
        )
        assert not any("files are not" in r for r in result.reasons)


# ── Made: reference resolution and would ────────────────────────────


class TestMadeReferences:
    async def test_unresolved_bought_item_id_reported(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.BoughtItemId"] = "999"
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert any("bought_item_id" in r and "does not resolve" in r for r in result.reasons)
        assert result.ok is False

    async def test_empty_reference_ids_are_not_reported(self):
        """An empty reference is "no link", never a dangling one: the add-in sends every
        mapped variable, blank ones included, and blank must not read as unresolved."""
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.BoughtItemId"] = ""
        variables["Glados.SourceItemId"] = "  "
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert not any("does not resolve" in r for r in result.reasons)

    async def test_unresolved_source_item_id_reported(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.SourceItemId"] = "999"
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert any("source_item_id" in r and "does not resolve" in r for r in result.reasons)

    async def test_unknown_article_group_ids_reported(self):
        rig = Rig(pdm_settings=make_pdm_settings(), article_groups=[make_article_group(id=1)])
        variables = dict(MADE_VARIABLES)
        variables["Glados.ArticleGroupIds"] = "1,2,3"
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert any("Unknown article group id(s)" in r for r in result.reasons)

    async def test_created_when_no_family_exists(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "created"
        assert result.ok is True
        assert result.reasons == []

    async def test_revised_when_family_exists_with_different_revision(self):
        existing = make_made_item(id=1, part_number="CAD-1001", revision="0")
        rig = Rig(pdm_settings=make_pdm_settings(), made_items=[existing])
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "revised"
        assert result.ok is True

    async def test_updated_when_family_exists_with_the_same_revision(self):
        existing = make_made_item(id=1, part_number="CAD-1001", revision="A")
        rig = Rig(pdm_settings=make_pdm_settings(), made_items=[existing])
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "updated"
        assert result.ok is True

    async def test_no_version_guard_even_when_already_at_a_newer_version(self):
        """Unlike IngestPdmFile, ValidatePdmPayload never looks at
        pdm_file_version at all: an item already linked at a version
        past the one being validated still gets a normal would verdict,
        never "skipped: already at version N"."""
        existing = make_made_item(
            id=1,
            part_number="CAD-1001",
            revision="A",
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=999,
        )
        rig = Rig(pdm_settings=make_pdm_settings(), made_items=[existing])
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables=dict(MADE_VARIABLES), vault_id="V1", file_id=100)
        )
        assert result.would == "updated"
        assert result.ok is True


# ── Bought: manufacturer requirement, would ─────────────────────────


class TestBoughtReferences:
    async def test_manufacturer_unresolved_on_create_is_a_reason(self):
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), suppliers=[])
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert "manufacturer unresolved" in result.reasons
        assert result.ok is False

    async def test_manufacturer_unresolved_on_existing_item_is_a_reason(self):
        existing = make_bought_item(id=1, part_number="CAD-2001", manufacturer_id=1)
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP),
            bought_items=[existing],
            suppliers=[],
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert "manufacturer unresolved" in result.reasons

    @pytest.mark.parametrize("raw", ["abc", "-3", "0"])
    async def test_malformed_edp_part_id_is_a_reason(self, raw):
        bought_map = {**BOUGHT_VAR_MAP, "edp_part_id": "Glados.EdpPartId"}
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=bought_map))
        variables = {**BOUGHT_VARIABLES, "Glados.EdpPartId": raw}
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert any("edp_part_id" in r for r in result.reasons)

    @pytest.mark.parametrize("raw", ["", "  ", "4711"])
    async def test_blank_or_numeric_edp_part_id_is_no_reason(self, raw):
        bought_map = {**BOUGHT_VAR_MAP, "edp_part_id": "Glados.EdpPartId"}
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=bought_map))
        variables = {**BOUGHT_VARIABLES, "Glados.EdpPartId": raw}
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert result.ok is True
        assert not any("edp_part_id" in r for r in result.reasons)

    async def test_created_when_no_match_at_all(self):
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP))
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert result.would == "created"
        assert result.ok is True

    async def test_claimed_when_a_web_candidate_matches(self):
        candidate = make_bought_item(
            id=1,
            part_number=None,
            manufacturer_id=1,
            order_code_1="OC-1",
            data_source=DataSource.WEB,
        )
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[candidate]
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert result.would == "claimed"
        assert result.ok is True

    async def test_claimed_when_a_cad_sourced_unlinked_candidate_matches(self):
        # Same rule as IngestPdmFile's own test: an add-in-created
        # row (data_source == "CAD" from creation, no pdm_file_id) must
        # still be reported as a claim, not silently missed by the dry run.
        candidate = make_bought_item(
            id=1,
            part_number=None,
            manufacturer_id=1,
            order_code_1="OC-1",
            data_source=DataSource.CAD,
        )
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[candidate]
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert result.would == "claimed"
        assert result.ok is True

    async def test_claimed_when_part_number_matches_an_unlinked_row(self):
        # Mirrors IngestPdmFile._ingest_bought's part-number-match branch:
        # a live row already carrying the incoming part number, with no
        # PDM link yet, would be claimed rather than updated in place.
        # The fixture item is never actually PDM-linked (pdm_file_id
        # defaults to None), so "claimed" is the behaviour this scenario
        # describes.
        existing = make_bought_item(id=1, part_number="CAD-2001", manufacturer_id=1)
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[existing]
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert result.would == "claimed"
        assert result.ok is True

    async def test_updated_when_linked_to_the_file_being_validated(self):
        existing = make_bought_item(
            id=1, part_number="CAD-2001", manufacturer_id=1, vault_id="V1", pdm_file_id=200
        )
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[existing]
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES), vault_id="V1", file_id=200)
        )
        assert result.would == "updated"
        assert result.ok is True

    async def test_unknown_with_reason_when_part_number_linked_to_another_file_and_identity_known(
        self,
    ):
        existing = make_bought_item(
            id=1, part_number="CAD-2001", manufacturer_id=1, vault_id="V1", pdm_file_id=999
        )
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[existing]
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES), vault_id="V1", file_id=200)
        )
        assert result.would == "unknown"
        assert "part number linked to another PDM file (id 999)" in result.reasons
        assert result.ok is False
        assert result.file_identity == "not_applicable"

    async def test_updated_never_another_file_when_identity_unresolved(self):
        # without a PDM file identity to compare against
        # (PAT surface, no file_path or no match), a row already linked to
        # a PDM file must never be reported as "linked to another" one;
        # that was a false positive, since the caller might well be
        # validating the very same file. It comes back as an in-place
        # update instead, with a note explaining why.
        existing = make_bought_item(
            id=1, part_number="CAD-2001", manufacturer_id=1, vault_id="V1", pdm_file_id=999
        )
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[existing]
        )
        result = await rig.use_case.execute(
            make_cmd(kind="bought", variables=dict(BOUGHT_VARIABLES))
        )
        assert result.would == "updated"
        assert result.ok is True
        assert not any("linked to another" in r for r in result.reasons)
        assert result.file_identity == "unresolved"
        assert "PDM file identity could not be resolved from the document path" in result.notes


class TestBoughtRevisionRequirement:
    """revision is data for a bought item, not part of its identity
    (docs/FIELD_OWNERSHIP.md principle 2), so its requirement is a Rule 1
    setting (AdminPdmSettings.required_fields["bought"]) rather than
    always-on the way it is for made items. Mirrors
    tests/unit/ingest_pdm_file/test_required_fields_and_validation.py's
    TestBoughtRevisionRequirement."""

    async def test_revision_missing_and_required_is_pending_not_a_reason(self):
        # Revision is PDM-owned even when the admin's selection requires it
        # for bought items, so a missing one lands in `pending_pdm` rather
        # than "identity variables missing", and `would` predicts the
        # normal bought create/claim outcome instead of being forced to
        # "unknown".
        pdm_settings = make_pdm_settings(
            bought_map=BOUGHT_VAR_MAP, required_fields={"made": [], "bought": ["revision"]}
        )
        rig = Rig(pdm_settings=pdm_settings)
        variables = dict(BOUGHT_VARIABLES)
        del variables["PDM.Revision"]
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert "identity variables missing" not in result.reasons
        assert result.ok is True
        assert result.pending_pdm == ["revision"]
        assert result.would == "created"
        assert result.revision is None

    async def test_would_created_when_not_required_and_absent(self):
        # Default fixture settings: required_fields={"bought": []}.
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP))
        variables = dict(BOUGHT_VARIABLES)
        del variables["PDM.Revision"]
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert "identity variables missing" not in result.reasons
        assert result.would == "created"
        assert result.ok is True
        assert result.pending_pdm == []
        assert result.revision is None


# ── Pending PDM fields (pre-release semantics) ───────────────────────


class TestPendingPdm:
    """part_number and revision (item_field_ownership owner "pdm") are
    always empty before a file is released. A missing PDM-owned field is
    reported in `pending_pdm`, in item_fields() order, never as a
    `reasons` entry, and `would` is predicted as if PDM had already
    assigned it."""

    async def test_made_item_missing_part_number_and_revision_is_ok(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables={"Glados.ArticleName": "Bracket"})
        )
        assert result.ok is True
        assert result.reasons == []
        assert result.pending_pdm == ["part_number", "revision"]
        assert result.would == "created"

    async def test_made_item_existing_family_empty_revision_is_revised(self):
        existing = make_made_item(id=1, part_number="CAD-1001", revision="0")
        rig = Rig(pdm_settings=make_pdm_settings(), made_items=[existing])
        variables = {"PDM.PartNumber": "CAD-1001", "Glados.ArticleName": "Bracket"}
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert result.ok is True
        assert result.pending_pdm == ["revision"]
        assert result.would == "revised"

    async def test_pdm_owned_configured_field_lands_in_pending_pdm(self):
        # revision_date is PDM-owned (item_field_ownership) but only a
        # configurable required field, not locked: an admin ticking it
        # required still routes a missing one to pending_pdm, never a
        # reason.
        pdm_settings = make_pdm_settings(required_fields={"made": ["revision_date"], "bought": []})
        rig = Rig(pdm_settings=pdm_settings)
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.ok is True
        assert result.reasons == []
        assert result.pending_pdm == ["revision_date"]
        assert result.would == "created"

    async def test_non_pdm_required_field_missing_still_fails_ok(self):
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        rig = Rig(pdm_settings=pdm_settings)
        result = await rig.use_case.execute(
            make_cmd(kind="made", variables={"Glados.ArticleName": "Bracket"})
        )
        assert result.ok is False
        assert result.reasons == ["required fields missing: material"]
        assert result.pending_pdm == ["part_number", "revision"]
        assert result.would == "created"

    async def test_bought_item_missing_part_number_uses_claim_create_logic(self):
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP))
        variables = {
            "Glados.ArticleName": "Bolt M6",
            "Glados.OrderCode1": "OC-1",
            "Glados.ManufacturerId": "1",
        }
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert result.ok is True
        assert result.pending_pdm == ["part_number"]
        assert result.would == "created"

    async def test_bought_item_missing_part_number_claims_existing_candidate(self):
        candidate = make_bought_item(
            id=1,
            part_number=None,
            manufacturer_id=1,
            order_code_1="OC-1",
            data_source=DataSource.WEB,
        )
        rig = Rig(
            pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP), bought_items=[candidate]
        )
        variables = {
            "Glados.ArticleName": "Bolt M6",
            "Glados.OrderCode1": "OC-1",
            "Glados.ManufacturerId": "1",
        }
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert result.ok is True
        assert result.pending_pdm == ["part_number"]
        assert result.would == "claimed"


# ── Required fields (docs/reference/pdm-ingest.md section 7) ────────────


class TestRequiredFields:
    """Mirrors IngestPdmFile's own required-field checks (see
    tests/unit/ingest_pdm_file/test_required_fields_and_validation.py's
    TestRequiredFields) through the shared evaluator: appended whenever
    `would` is created/revised/claimed/unknown, never for updated."""

    async def test_reason_appended_when_locked_field_missing_on_create(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        del variables["Glados.ArticleName"]
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert result.would == "created"
        assert "required fields missing: article_name" in result.reasons
        assert result.ok is False

    async def test_reason_appended_when_configured_field_missing_on_create(self):
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        rig = Rig(pdm_settings=pdm_settings)
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "created"
        # MADE_VAR_MAP maps material to Glados.Material, but this suite's
        # own MADE_VARIABLES never sets it: present in settings, absent
        # on the file, so the bare (unannotated) descriptor is used.
        assert "required fields missing: material" in result.reasons
        assert result.ok is False

    async def test_reason_annotated_when_configured_field_has_no_variable_mapped(self):
        made_map = dict(MADE_VAR_MAP)
        made_map["material"] = ""
        pdm_settings = make_pdm_settings(
            made_map=made_map, required_fields={"made": ["material"], "bought": []}
        )
        rig = Rig(pdm_settings=pdm_settings)
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert "required fields missing: material (no PDM variable mapped)" in result.reasons

    async def test_no_reason_when_nothing_extra_configured(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "created"
        assert not any("required fields missing" in r for r in result.reasons)
        assert result.ok is True

    async def test_reason_appended_on_revised(self):
        existing = make_made_item(id=1, part_number="CAD-1001", revision="0")
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        rig = Rig(pdm_settings=pdm_settings, made_items=[existing])
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "revised"
        assert "required fields missing: material" in result.reasons

    async def test_not_checked_when_updated(self):
        existing = make_made_item(id=1, part_number="CAD-1001", revision="A")
        pdm_settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        rig = Rig(pdm_settings=pdm_settings, made_items=[existing])
        result = await rig.use_case.execute(make_cmd(kind="made", variables=dict(MADE_VARIABLES)))
        assert result.would == "updated"
        assert not any("required fields missing" in r for r in result.reasons)
        assert result.ok is True

    async def test_reason_appended_when_bought_locked_field_missing(self):
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP))
        variables = dict(BOUGHT_VARIABLES)
        del variables["Glados.OrderCode1"]
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert result.would == "created"
        assert "required fields missing: order_code_1" in result.reasons


class TestProcessRoleRequired:
    """mirrors IngestPdmFile's own check (see
    tests/unit/ingest_pdm_file/test_required_fields_and_validation.py's
    TestProcessRoleRequired), checked at the same
    would-created/revised/claimed/unknown gate as required fields."""

    async def test_reason_appended_when_a_process_entry_has_no_role_on_create(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.Processes"] = '[{"fabrication_method_id":1,"group_index":0}]'
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert result.would == "created"
        assert "process entry without role" in result.reasons
        assert result.ok is False

    async def test_not_checked_for_bought_items(self):
        # parse_processes/process_entry_missing_role is made-item only;
        # a bought payload never carries a processes routing at all.
        rig = Rig(pdm_settings=make_pdm_settings(bought_map=BOUGHT_VAR_MAP))
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Processes"] = '[{"fabrication_method_id":1,"group_index":0}]'
        result = await rig.use_case.execute(make_cmd(kind="bought", variables=variables))
        assert not any("process entry" in r for r in result.reasons)

    async def test_not_checked_when_updated(self):
        existing = make_made_item(id=1, part_number="CAD-1001", revision="A")
        rig = Rig(pdm_settings=make_pdm_settings(), made_items=[existing])
        variables = dict(MADE_VARIABLES)
        variables["Glados.Processes"] = '[{"fabrication_method_id":1,"group_index":0}]'
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert result.would == "updated"
        assert not any("process entry" in r for r in result.reasons)

    async def test_no_reason_when_every_entry_has_a_role(self):
        rig = Rig(pdm_settings=make_pdm_settings())
        variables = dict(MADE_VARIABLES)
        variables["Glados.Processes"] = (
            '[{"role":"fabrication","fabrication_method_id":1,"group_index":0}]'
        )
        result = await rig.use_case.execute(make_cmd(kind="made", variables=variables))
        assert not any("process entry" in r for r in result.reasons)
