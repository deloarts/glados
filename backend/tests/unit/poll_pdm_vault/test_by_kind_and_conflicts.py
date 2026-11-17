"""
The by_kind folder's kind resolution, the file-type admission rule, the
documents folder's routing to PdmDocumentSync, and the explicit-folder
kind/link conflict rules.
"""

from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from tests.unit.poll_pdm_vault._helpers import BOUGHT_FOLDER
from tests.unit.poll_pdm_vault._helpers import BOUGHT_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import BY_KIND_FOLDER
from tests.unit.poll_pdm_vault._helpers import BY_KIND_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import DOCUMENTS_FOLDER
from tests.unit.poll_pdm_vault._helpers import DOCUMENTS_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import ROOT_ID
from tests.unit.poll_pdm_vault._helpers import make_folder
from tests.unit.poll_pdm_vault._helpers import make_object
from tests.unit.poll_pdm_vault._helpers import make_pdm_settings
from tests.unit.poll_pdm_vault._helpers import make_snapshot
from tests.unit.poll_pdm_vault.rig import FakeDocumentSync
from tests.unit.poll_pdm_vault.rig import Rig


class TestByKindFolder:
    """A `by_kind` folder (docs/FIELD_OWNERSHIP.md, principle 1) never
    asserts its own kind; it is resolved from the file's
    `Glados.Kind` (default) datacard variable once fetched."""

    async def test_new_file_resolves_made_from_kind_variable(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(id=1, path="\\Parts\\part.sldprt", parent_folder_id=BY_KIND_FOLDER_ID)
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "made"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.ingested == 1
        assert rig.ingest.calls[0].kind == "made"

    async def test_new_file_resolves_bought_from_kind_variable(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(id=1, path="\\Parts\\part.sldprt", parent_folder_id=BY_KIND_FOLDER_ID)
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "bought"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.ingested == 1
        assert rig.ingest.calls[0].kind == "bought"

    async def test_empty_kind_variable_is_skipped_without_ingest(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(id=1, path="\\Parts\\part.sldprt", parent_folder_id=BY_KIND_FOLDER_ID)
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": ""}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        assert rig.ingest.calls == []
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.kind is None
        assert row.sync_state == PdmFileSyncState.SKIPPED.value
        assert row.last_error == "kind not set"

    async def test_unknown_kind_value_is_skipped_with_value_in_message(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(id=1, path="\\Parts\\part.sldprt", parent_folder_id=BY_KIND_FOLDER_ID)
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "weldment"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.last_error is not None
        assert "weldment" in row.last_error

    async def test_unchanged_file_under_a_by_kind_folder_is_untouched(self) -> None:
        existing = make_snapshot(
            file_id=1, kind="made", path="\\Parts\\part.sldprt", version=5, state_id=10
        )
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]), snapshots=[existing]
        )
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(
                id=1,
                path="\\Parts\\part.sldprt",
                parent_folder_id=BY_KIND_FOLDER_ID,
                version=5,
                state_id=10,
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.changed == 0
        assert rig.gateway.variables_calls == []
        assert rig.ingest.calls == []


class TestFileTypeRule:
    """The file type rule (docs/reference/pdm-documents.md section 1): only files
    whose extension the resolved (or, for by_kind, the unioned) kind
    admits are ever snapshotted at all; everything else is tallied into
    `ignored_by_type` and never reaches the diff."""

    async def test_made_folder_ignores_a_non_admitted_extension(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[MADE_FOLDER]))
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, name="part.sldasm", path="\\Made-Parts\\part.sldasm")
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 0
        assert summary.ignored_by_type == 1
        assert rig.ingest.calls == []
        assert rig.snapshot_repo.get("V1", 1) is None

    async def test_bought_folder_admits_sldasm_by_default(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BOUGHT_FOLDER]))
        rig.gateway.folders[BOUGHT_FOLDER_ID] = [
            make_object(id=1, name="assembly.sldasm", path="\\Bought-Parts\\assembly.sldasm")
        ]

        summary = await rig.use_case.execute()

        assert summary.ignored_by_type == 0
        assert summary.ingested == 1
        assert rig.ingest.calls[0].kind == "bought"

    async def test_by_kind_folder_admits_the_union_at_walk_time(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(
                id=1,
                name="assembly.sldasm",
                path="\\Parts\\assembly.sldasm",
                parent_folder_id=BY_KIND_FOLDER_ID,
            )
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "bought"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.ignored_by_type == 0
        assert summary.ingested == 1
        assert rig.ingest.calls[0].kind == "bought"

    async def test_by_kind_folder_rechecks_the_resolved_kinds_own_extensions(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(
                id=1,
                name="assembly.sldasm",
                path="\\Parts\\assembly.sldasm",
                parent_folder_id=BY_KIND_FOLDER_ID,
            )
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "made"}
            )
        ]

        summary = await rig.use_case.execute()

        # It WAS snapshotted (the union admitted it at walk time); only
        # the recheck after resolving "made" rejects it, so this is a
        # skip, never an ignored_by_type.
        assert summary.ignored_by_type == 0
        assert summary.skipped == 1
        assert rig.ingest.calls == []
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.last_error == "sldasm files are not made items"


class TestDocumentsFolder:
    """A `documents` watched folder never asserts made/bought identity:
    every file in it is a document candidate handed to PdmDocumentSync,
    never to IngestPdmFile."""

    def _seed_documents_folder(self, rig: "Rig", *objects: PdmObjectInfo) -> None:
        rig.gateway.folders[ROOT_ID] = [
            *rig.gateway.folders[ROOT_ID],
            make_folder(
                id=DOCUMENTS_FOLDER_ID,
                name="Exported Documents",
                path="\\Exported Documents",
            ),
        ]
        rig.gateway.folders[DOCUMENTS_FOLDER_ID] = list(objects)

    async def test_files_are_routed_to_document_sync_not_ingest(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]))
        self._seed_documents_folder(
            rig,
            make_object(
                id=1,
                name="CAD-1_A.pdf",
                path="\\Exported Documents\\CAD-1_A.pdf",
                parent_folder_id=DOCUMENTS_FOLDER_ID,
            ),
        )

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.documents == 1
        assert rig.ingest.calls == []
        assert len(rig.document_sync.calls) == 1
        assert rig.document_sync.calls[0].id == 1
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.kind == "document"
        # The scan-time upsert stamps "document" as the kind and PENDING
        # as the sync_state; PdmDocumentSync.sync_one (a fake here, see
        # tests/unit/test_pdm_documents.py for the real one's own outcome
        # bookkeeping) owns the outcome fields, not the poller itself,
        # the same division of labour IngestPdmFile has for made/bought.

    async def test_every_extension_is_admitted_no_file_type_filter(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]))
        self._seed_documents_folder(
            rig,
            make_object(
                id=1,
                name="whatever.xyz",
                path="\\Exported Documents\\whatever.xyz",
                parent_folder_id=DOCUMENTS_FOLDER_ID,
            ),
        )

        summary = await rig.use_case.execute()

        assert summary.ignored_by_type == 0
        assert summary.files_seen == 1

    async def test_document_error_outcome_is_tallied(self) -> None:
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]),
            document_sync=FakeDocumentSync(default_action="document_error"),
        )
        self._seed_documents_folder(
            rig,
            make_object(
                id=1,
                name="CAD-1_A.pdf",
                path="\\Exported Documents\\CAD-1_A.pdf",
                parent_folder_id=DOCUMENTS_FOLDER_ID,
            ),
        )

        summary = await rig.use_case.execute()

        assert summary.document_errors == 1
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.kind == "document"

    async def test_skipped_outcome_is_tallied_as_skipped_not_document(self) -> None:
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]),
            document_sync=FakeDocumentSync(default_action="skipped"),
        )
        self._seed_documents_folder(
            rig,
            make_object(
                id=1,
                name="CAD-1_A.pdf",
                path="\\Exported Documents\\CAD-1_A.pdf",
                parent_folder_id=DOCUMENTS_FOLDER_ID,
            ),
        )

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        assert summary.documents == 0
        assert summary.document_errors == 0

    async def test_unchanged_document_is_not_resynced(self) -> None:
        existing = make_snapshot(
            file_id=1,
            kind="document",
            path="\\Exported Documents\\CAD-1_A.pdf",
            version=3,
            state_id=10,
        )
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]), snapshots=[existing]
        )
        self._seed_documents_folder(
            rig,
            make_object(
                id=1,
                name="CAD-1_A.pdf",
                path="\\Exported Documents\\CAD-1_A.pdf",
                parent_folder_id=DOCUMENTS_FOLDER_ID,
                version=3,
                state_id=10,
            ),
        )

        summary = await rig.use_case.execute()

        assert summary.changed == 0
        assert rig.document_sync.calls == []


class TestExplicitFolderKindDatacardDisagreement:
    """The SolidWorks add-in is the first guard against a kind variable
    disagreeing with an explicit made/bought folder; this is the poller's
    own backstop, resolved once the file's variables are read, separate
    from the snapshot-vs-folder link conflict below, which needs no
    variables read at all."""

    async def test_disagreeing_variable_is_a_conflict_without_ingest(self) -> None:
        rig = Rig()  # default watched_folders = [MADE_FOLDER]
        obj = make_object(id=1, path="\\Made-Parts\\part.sldprt")
        rig.gateway.folders[MADE_FOLDER_ID] = [obj]
        # Also resolvable by id, since a same-run conflict is immediately
        # retried by _retry_conflicts (docs/reference/field-ownership.md section 5); the
        # disagreement reproduces identically on that retry.
        rig.gateway.by_id[1] = obj
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "bought"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.conflicts == 2  # detected, then reproduced on the same-run retry
        assert rig.ingest.calls == []
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.CONFLICT.value
        assert row.last_error == "kind variable says bought, folder says made"

    async def test_agreeing_variable_proceeds_normally(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, path="\\Made-Parts\\part.sldprt")]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "made"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.ingested == 1
        assert rig.ingest.calls[0].kind == "made"


class TestExplicitFolderLinkConflict:
    """A file's snapshot already resolved a kind (from a previous, real
    ingest) that disagrees with the explicit folder it is found under this
    run. Needs no datacard read at all; it is caught before _ingest_one is
    ever called."""

    async def test_linked_file_in_the_wrong_kind_folder_is_a_conflict(self) -> None:
        """A conflict freshly detected during the ordinary walk is also
        retried at the end of the very same run (the same "detected, then
        reproduced" pattern the datacard-kind-variable conflict already
        has; see TestExplicitFolderKindDatacardDisagreement), so
        `by_id` is wired up too, and it still resolves as a conflict the
        second time around."""
        existing = make_snapshot(
            file_id=1, kind="made", path="\\Made-Parts\\shared.sldprt", item_id=42
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[BOUGHT_FOLDER]), snapshots=[existing])
        obj = make_object(
            id=1, path="\\Bought-Parts\\shared.sldprt", parent_folder_id=BOUGHT_FOLDER_ID
        )
        rig.gateway.folders[BOUGHT_FOLDER_ID] = [obj]
        rig.gateway.by_id[1] = obj

        summary = await rig.use_case.execute()

        assert summary.conflicts == 2  # detected, then reproduced on the same-run retry
        assert rig.ingest.calls == []
        assert rig.gateway.variables_calls == []  # no datacard read needed for this check
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.CONFLICT.value
        assert row.last_error == "linked as made, now in a bought folder"
        run_id = next(iter(rig.run_repo.runs))
        entries = [e for e in rig.run_repo.entries[run_id] if e.action == "conflict"]
        assert len(entries) == 2
        assert entries[0].item_id == 42

    async def test_unlinked_file_in_a_different_kind_folder_adopts_the_new_kind(self) -> None:
        existing = make_snapshot(
            file_id=1,
            kind="made",
            path="\\Made-Parts\\shared.sldprt",
            item_id=None,
            sync_state=PdmFileSyncState.SKIPPED,
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[BOUGHT_FOLDER]), snapshots=[existing])
        rig.gateway.folders[BOUGHT_FOLDER_ID] = [
            make_object(
                id=1, path="\\Bought-Parts\\shared.sldprt", parent_folder_id=BOUGHT_FOLDER_ID
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.conflicts == 0
        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].kind == "bought"
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.kind == "bought"

    async def test_by_kind_folder_is_never_a_link_conflict(self) -> None:
        existing = make_snapshot(file_id=1, kind="made", path="\\Parts\\shared.sldprt", item_id=42)
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]), snapshots=[existing]
        )
        rig.gateway.folders[BY_KIND_FOLDER_ID] = [
            make_object(
                id=1,
                path="\\Parts\\shared.sldprt",
                parent_folder_id=BY_KIND_FOLDER_ID,
                version=6,
            )
        ]
        rig.gateway.variables[1] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        summary = await rig.use_case.execute()

        assert summary.conflicts == 0
