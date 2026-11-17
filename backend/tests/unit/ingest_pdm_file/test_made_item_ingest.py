"""
Unit tests for TestMadeCreate, TestMadeRevise, TestMadeInPlaceUpdate,
TestSourceItemShadowRule and TestArticleGroupWarning. No database, no
HTTP. All dependencies replaced with in-memory fakes.
"""

import pytest

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.domain.events.pdm_events import PdmFileIngested
from src.modules.external_data.domain.events.pdm_events import PdmIngestConflict
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.unit.ingest_pdm_file._helpers import MADE_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_article_group
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_made_item_settings
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file._helpers import make_source_item
from tests.unit.ingest_pdm_file.fakes import FakePartNumberRegistry
from tests.unit.ingest_pdm_file.rig import Rig


class TestMadeCreate:
    async def test_creates_new_made_item(self):
        rig = Rig()
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        assert outcome.item_id is not None
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.part_number == "CAD-1001"
        assert item.revision == "A"
        assert item.data_source == DataSource.CAD.value
        assert item.status == MadeItemCatalogueStatus.ACTIVE.value
        assert item.vault_id == "V1"
        assert item.pdm_file_id == 100
        assert item.pdm_file_version == 5
        assert item.pdm_sync_state == PdmSyncState.SYNCED.value
        assert item.mass == 123  # "123,4" -> comma decimal -> rounded
        assert item.changes  # changelog line written
        # One transaction: CreateMadeItem's own write closure and the PDM
        # link-column patch commit together.
        assert rig.uow.commits == 1
        # MadeItemCreated (from CreateMadeItem's closure) + PdmFileIngested
        # (from the link-column write), both staged in the same commit.
        assert len(rig.bus.published) == 2
        event = rig.bus.published[-1]
        assert isinstance(event, PdmFileIngested)
        assert event.action == "created"
        assert event.part_number == "CAD-1001"

        snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
        assert snapshot.sync_state == PdmFileSyncState.INGESTED.value
        assert snapshot.item_id == outcome.item_id
        assert snapshot.last_ingested_version == 5

    async def test_creates_even_when_web_creation_is_disabled(self):
        """The admin switch only restricts web users; ingest runs as the
        system user and must still create PDM-numbered rows."""
        rig = Rig(made_item_settings=make_made_item_settings(web_creation_allowed=False))
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        assert await rig.made_item_repo.get_by_id(outcome.item_id) is not None

    async def test_keeps_the_pdm_part_number_when_auto_numbering_is_on(self):
        rig = Rig(made_item_settings=make_made_item_settings(part_number_auto=True))
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.part_number == "CAD-1001"
        assert rig.registry.entries.get("CAD-1001") == "made"

    async def test_label_and_feature_tree_variables_are_never_read_into_the_item(self):
        """A label (item_field_ownership.MADE_ITEM_LABEL_FIELDS) and the
        feature-tree render field are mappable, add-in-written rows ingest
        must never read (map_variables() excludes them): mapping them and
        writing a value for them on the card must not affect ingest at
        all, since MadeItem has no such attributes to receive them."""
        pdm_settings = make_pdm_settings(
            made_map={
                **MADE_VAR_MAP,
                "article_group_names": "Glados.ArticleGroupNames",
                "process_names": "Glados.ProcessNames",
                "source_item_name": "Glados.SourceItemName",
                "feature_tree_representation": "Glados.FeatureTreeRepresentation",
            }
        )
        rig = Rig(pdm_settings=pdm_settings)
        payload = make_payload(
            kind="made",
            variables={
                **MADE_VARIABLES,
                "Glados.ArticleGroupNames": "Group A",
                "Glados.ProcessNames": "Turning",
                "Glados.SourceItemName": "Rod 10x100",
                "Glados.FeatureTreeRepresentation": "CAD-1001 RevA (Bracket)",
            },
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.article_name == "Bracket"
        assert not hasattr(item, "article_group_names")
        assert not hasattr(item, "process_names")
        assert not hasattr(item, "source_item_name")
        assert not hasattr(item, "feature_tree_representation")

    async def test_part_number_clash_parks_conflict(self):
        registry = FakePartNumberRegistry(preclaimed={"CAD-1001": "bought"})
        rig = Rig(registry=registry)
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))
        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "conflict"
        assert await rig.made_item_repo.get_by_id(1) is None  # nothing created
        snapshot = await rig.snapshot_repo.get_by_file("V1", 100)
        assert snapshot.sync_state == PdmFileSyncState.CONFLICT.value
        assert snapshot.parked_payload is not None
        assert snapshot.parked_payload["part_number"] == "CAD-1001"
        assert len(rig.bus.published) == 1
        assert isinstance(rig.bus.published[0], PdmIngestConflict)

    async def test_exception_after_create_but_before_link_write_rolls_back(self, monkeypatch):
        """An error raised while patching in the PDM link columns (here,
        the snapshot upsert) must roll back the whole merged transaction,
        not just fail to finish it. CreateMadeItem's own write and the
        link-column patch are one commit, so a crash between them
        cannot leave a stray committed row without its PDM link."""
        rig = Rig()
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        def _raise(*_args, **_kwargs):
            raise RuntimeError("snapshot upsert exploded")

        monkeypatch.setattr(rig.snapshot_repo, "upsert_many", _raise)

        with pytest.raises(RuntimeError, match="snapshot upsert exploded"):
            await rig.use_case.execute(payload)

        assert rig.uow.commits == 0
        assert rig.uow.rollbacks >= 1

        # The rollback discarded the item CreateMadeItem's own write() had
        # already staged, so the same rig, retried with the same payload,
        # must create the item exactly once rather than conflicting with
        # a stray un-rolled-back row.
        monkeypatch.undo()
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "created"
        assert await rig.made_item_repo.get_by_id(outcome.item_id) is not None
        assert len(await rig.made_item_repo.get_family("CAD-1001")) == 1


class TestMadeRevise:
    async def test_revision_change_creates_new_revision_row(self):
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
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "revised"
        new_item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert new_item.revision == "B"
        assert new_item.part_number == "CAD-1001"
        assert new_item.data_source == DataSource.CAD.value
        assert new_item.pdm_file_version == 2

        predecessor = await rig.made_item_repo.get_by_id(1)
        assert predecessor.status == MadeItemCatalogueStatus.REPLACED.value
        assert predecessor.successor_item_id == new_item.id
        # One transaction: CreateMadeItemRevision's own write closure and
        # the PDM link-column patch commit together.
        assert rig.uow.commits == 1

    async def test_exception_after_revise_but_before_link_write_rolls_back(self, monkeypatch):
        """Same crash-safety property as TestMadeCreate's matching test,
        for the revise path: CreateMadeItemRevision's own write and the
        link-column patch are one commit, so a failure patching in the PDM
        link columns rolls back the whole thing, predecessor update
        included."""

        def make_source():
            return make_made_item(
                1,
                part_number="CAD-1001",
                revision="A",
                data_source=DataSource.CAD,
                vault_id="V1",
                pdm_file_id=100,
                pdm_file_version=1,
            )

        rig = Rig(made_items=[make_source()])
        variables = dict(MADE_VARIABLES)
        variables["PDM.Revision"] = "B"
        payload = make_payload(kind="made", file_version=2, variables=variables)

        def _raise(*_args, **_kwargs):
            raise RuntimeError("snapshot upsert exploded")

        monkeypatch.setattr(rig.snapshot_repo, "upsert_many", _raise)

        with pytest.raises(RuntimeError, match="snapshot upsert exploded"):
            await rig.use_case.execute(payload)

        assert rig.uow.commits == 0
        assert rig.uow.rollbacks >= 1

        # The rollback discarded the new revision row and the predecessor
        # update CreateMadeItemRevision's own write() had already staged,
        # so the same rig, retried with the same payload, must produce
        # exactly one new revision B row rather than conflicting with (or
        # duplicating) a stray un-rolled-back one.
        monkeypatch.undo()
        outcome = await rig.use_case.execute(payload)
        assert outcome.action == "revised"
        family = await rig.made_item_repo.get_family("CAD-1001")
        assert len(family) == 2
        assert len([item for item in family if item.revision == "B"]) == 1


class TestMadeInPlaceUpdate:
    async def test_only_in_place_flagged_fields_change(self):
        # default_policy(): pdm_update_in_place = {mass, note, weblink,
        # article_group_ids, revision_date, revision_note}; article_name
        # and material are NOT in that set and must stay untouched.
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
            article_name="Old name",
        )
        item.material = "OLD-MATERIAL"
        rig = Rig(made_items=[item])
        variables = dict(MADE_VARIABLES)
        variables["Glados.ArticleName"] = "New name"
        variables["Glados.Material"] = "NEW-MATERIAL"
        variables["Glados.Note"] = "updated note"
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"
        updated = await rig.made_item_repo.get_by_id(1)
        assert updated.article_name == "Old name"  # not policy-flagged: untouched
        assert updated.material == "OLD-MATERIAL"  # not policy-flagged: untouched
        assert updated.note == "updated note"  # policy-flagged: applied
        assert updated.pdm_file_version == 2
        assert updated.pdm_sync_state == PdmSyncState.SYNCED.value
        assert rig.uow.commits == 1  # single transaction, no sub-use-case involved
        assert len(rig.bus.published) == 1

    async def test_no_in_place_changes_is_skipped_but_link_columns_bumped(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        item.note = "from CAD"  # already equal to MADE_VARIABLES' mapped note
        item.mass = 123  # already equal to MADE_VARIABLES' mass (rounds to 123)
        rig = Rig(made_items=[item])
        payload = make_payload(kind="made", file_version=2, variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "skipped"
        assert outcome.message == "no in-place changes"
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.pdm_file_version == 2  # link columns still bumped
        assert stored.pdm_sync_state == PdmSyncState.SYNCED.value
        assert rig.bus.published == []  # nothing meaningfully ingested

    async def test_exception_from_repo_propagates_and_nothing_committed(self):
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
        rig.made_item_repo.raise_on_save = RuntimeError("db exploded")
        variables = dict(MADE_VARIABLES)
        variables["Glados.Note"] = "brand new note"
        payload = make_payload(kind="made", file_version=2, variables=variables)

        with pytest.raises(RuntimeError, match="db exploded"):
            await rig.use_case.execute(payload)

        assert rig.uow.commits == 0
        assert await rig.snapshot_repo.get_by_file("V1", 100) is None


class TestSourceItemShadowRule:
    async def test_web_edit_survives_unchanged_cad_value(self):
        source = make_source_item(id=7)
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
            source_item_id=99,
            pdm_source_item_id=7,
        )
        rig = Rig(made_items=[item], source_items=[source])
        variables = dict(MADE_VARIABLES)
        variables["Glados.SourceItemId"] = "7"  # same as the stored shadow
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.source_item_id == 99  # web edit preserved
        assert stored.pdm_source_item_id == 7  # shadow unchanged
        assert "source_item_id" not in outcome.message or outcome.action == "skipped"

    async def test_changed_cad_value_overrides_web_edit(self):
        other_source = make_source_item(id=8)
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
            source_item_id=99,
            pdm_source_item_id=7,
        )
        rig = Rig(made_items=[item], source_items=[other_source])
        variables = dict(MADE_VARIABLES)
        variables["Glados.SourceItemId"] = "8"  # differs from the stored shadow (7)
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"
        stored = await rig.made_item_repo.get_by_id(1)
        assert stored.source_item_id == 8
        assert stored.pdm_source_item_id == 8


class TestArticleGroupWarning:
    async def test_unknown_ids_are_dropped_with_a_note(self):
        known = make_article_group(1)
        rig = Rig(article_groups=[known])
        variables = dict(MADE_VARIABLES)
        variables["Glados.ArticleGroupIds"] = "1,999"
        payload = make_payload(kind="made", variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.article_group_ids == [1]
        assert "999" in outcome.message


class TestPartNumberFollowsPdm:
    """PDM owns a linked row's part number: a drifted number heals on the
    file's next ingest, also when the file is otherwise in sync."""

    @staticmethod
    def _drifted_family() -> list:
        return [
            make_made_item(
                1,
                part_number="G-26-00004",
                revision="A",
                data_source=DataSource.CAD,
                vault_id="V1",
                pdm_file_id=100,
                pdm_file_version=5,
            )
        ]

    async def test_in_sync_file_renumbers_its_item(self):
        registry = FakePartNumberRegistry({"G-26-00004": "made"})
        rig = Rig(made_items=self._drifted_family(), registry=registry)

        outcome = await rig.use_case.execute(
            make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        )

        assert outcome.action == "updated"
        assert outcome.item_id == 1
        assert "from G-26-00004 to CAD-1001" in outcome.message
        item = await rig.made_item_repo.get_by_id(1)
        assert item.part_number == "CAD-1001"
        assert "Part number changed by PDM from G-26-00004 to CAD-1001." in str(item.changes)
        # The old number stays registered: part numbers are never reused.
        assert registry.entries == {"G-26-00004": "made", "CAD-1001": "made"}

    async def test_number_owned_by_another_item_parks_a_conflict(self):
        registry = FakePartNumberRegistry({"G-26-00004": "made", "CAD-1001": "bought"})
        rig = Rig(made_items=self._drifted_family(), registry=registry)

        outcome = await rig.use_case.execute(
            make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        )

        assert outcome.action == "conflict"
        assert "already belongs to another item" in outcome.message
        assert (await rig.made_item_repo.get_by_id(1)).part_number == "G-26-00004"

    async def test_renumbering_is_noted_on_a_regular_update(self):
        family = self._drifted_family()
        family[0].pdm_file_version = 4
        rig = Rig(made_items=family, registry=FakePartNumberRegistry({"G-26-00004": "made"}))

        outcome = await rig.use_case.execute(
            make_payload(kind="made", file_version=5, variables=dict(MADE_VARIABLES))
        )

        assert outcome.message.startswith("part number changed by PDM from G-26-00004")
        assert (await rig.made_item_repo.get_by_id(1)).part_number == "CAD-1001"
