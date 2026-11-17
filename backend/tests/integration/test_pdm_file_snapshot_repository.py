"""
DB-backed coverage for SqlAlchemyPdmFileSnapshotRepository: upsert_many
(insert then update, matched on vault_id + file_id), get_by_file, get_multi
(sync_state/kind/search filters, last_seen_at desc paging),
get_all_for_vault (the whole-vault load PollPdmVault's rewritten walk
diffs against, unpaged and scoped to one vault), list_conflicts,
reset_skipped_to_pending, counts_by_state and save.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    PdmFileSnapshotFilterDto,
)

_NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _snapshot(
    *,
    vault_id: str = "V1",
    file_id: int,
    kind: str | None = "made",
    name: str = "Bracket.SLDPRT",
    path: str = "\\Made-Parts\\Bracket.SLDPRT",
    version: int = 1,
    state_id: int = 1,
    state: str = "Released",
    last_seen_at: datetime = _NOW,
    sync_state: PdmFileSyncState = PdmFileSyncState.PENDING,
    part_number: str | None = None,
    revision: str | None = None,
    item_id: int | None = None,
    parked_payload: dict[str, str] | None = None,
    last_error: str | None = None,
) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=0,
        vault_id=vault_id,
        file_id=file_id,
        kind=kind,
        name=name,
        path=path,
        parent_folder_id=1,
        version=version,
        state_id=state_id,
        state=state,
        modified_at=None,
        first_seen_at=_NOW,
        last_seen_at=last_seen_at,
        last_ingested_version=None,
        sync_state=sync_state,
        last_error=last_error,
        part_number=part_number,
        revision=revision,
        item_id=item_id,
        parked_payload=parked_payload,
    )


class TestUpsertMany:
    async def test_inserts_new_rows(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1), _snapshot(file_id=2)])
        await db.commit()

        assert await repo.get_by_file("V1", 1) is not None
        assert await repo.get_by_file("V1", 2) is not None

    async def test_updates_existing_row_matched_on_vault_and_file(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, version=1, state="Work in progress")])
        await db.commit()

        await repo.upsert_many([_snapshot(file_id=1, version=2, state="Released")])
        await db.commit()

        result = await repo.get_by_file("V1", 1)
        assert result is not None
        assert result.version == 2
        assert result.state == "Released"
        # No duplicate row was created.
        total, rows = await repo.get_multi(PdmFileSnapshotFilterDto())
        assert total == 1
        assert len(rows) == 1


class TestNullableKind:
    """A file under a `by_kind` watched folder has no resolved kind until
    its datacard variables are read (docs/FIELD_OWNERSHIP.md, principle
    1). The column must accept and round-trip NULL."""

    async def test_inserts_a_row_with_null_kind(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, kind=None)])
        await db.commit()

        result = await repo.get_by_file("V1", 1)
        assert result is not None
        assert result.kind is None

    async def test_updates_kind_from_null_to_resolved(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, kind=None)])
        await db.commit()

        await repo.upsert_many([_snapshot(file_id=1, kind="made")])
        await db.commit()

        result = await repo.get_by_file("V1", 1)
        assert result is not None
        assert result.kind == "made"


class TestGetByFile:
    async def test_returns_none_when_missing(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        assert await repo.get_by_file("V1", 999) is None

    async def test_scoped_to_vault_id(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(vault_id="V1", file_id=1)])
        await db.commit()

        assert await repo.get_by_file("V2", 1) is None
        assert await repo.get_by_file("V1", 1) is not None


class TestFindByPathSuffix:
    """resolving a PAT caller's full local document path
    (drive letter and vault view root included) to a snapshot row via its
    own vault-relative path."""

    async def test_matches_a_full_local_path_by_suffix(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, path="\\Made-Parts\\Bracket.SLDPRT")])
        await db.commit()

        result = await repo.find_by_path_suffix("V1", "c:\\demo-vault\\made-parts\\bracket.sldprt")

        assert result is not None
        assert result.file_id == 1

    async def test_case_insensitive(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, path="\\Made-Parts\\Bracket.SLDPRT")])
        await db.commit()

        result = await repo.find_by_path_suffix(
            "V1", "C:\\DEMO-VAULT\\MADE-PARTS\\BRACKET.SLDPRT".lower()
        )

        assert result is not None
        assert result.file_id == 1

    async def test_returns_none_when_nothing_matches(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, path="\\Made-Parts\\Bracket.SLDPRT")])
        await db.commit()

        assert await repo.find_by_path_suffix("V1", "c:\\demo-vault\\other\\thing.sldprt") is None

    async def test_scoped_to_vault_id(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [_snapshot(vault_id="V2", file_id=1, path="\\Made-Parts\\Bracket.SLDPRT")]
        )
        await db.commit()

        result = await repo.find_by_path_suffix("V1", "c:\\demo-vault\\made-parts\\bracket.sldprt")

        assert result is None

    async def test_prefers_the_longest_match(self, db):
        # A shallower watched folder's own path is always a suffix of a
        # deeper file's path too, so the deepest (longest) match is the
        # real one.
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, path="\\Bracket.SLDPRT"),
                _snapshot(file_id=2, path="\\Made-Parts\\Bracket.SLDPRT"),
            ]
        )
        await db.commit()

        result = await repo.find_by_path_suffix("V1", "c:\\demo-vault\\made-parts\\bracket.sldprt")

        assert result is not None
        assert result.file_id == 2

    async def test_ambiguous_tie_returns_none(self, db):
        # Two rows whose own path is the identical, equally-long match:
        # there is then no reliable way to tell which file is meant.
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, path="\\Made-Parts\\Bracket.SLDPRT"),
                _snapshot(file_id=2, path="\\Made-Parts\\Bracket.SLDPRT"),
            ]
        )
        await db.commit()

        result = await repo.find_by_path_suffix("V1", "c:\\demo-vault\\made-parts\\bracket.sldprt")

        assert result is None

    async def test_a_row_longer_than_the_suffix_is_ignored(self, db):
        # A stored path longer than the caller's suffix can never be one
        # of its suffixes, so it must be filtered out, not just fail the
        # endswith check.
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [_snapshot(file_id=1, path="\\Made-Parts\\Subfolder\\Bracket.SLDPRT")]
        )
        await db.commit()

        result = await repo.find_by_path_suffix("V1", "c:\\bracket.sldprt")

        assert result is None


class TestGetMulti:
    async def test_filters_by_sync_state(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, sync_state=PdmFileSyncState.PENDING),
                _snapshot(file_id=2, sync_state=PdmFileSyncState.INGESTED),
            ]
        )
        await db.commit()

        total, rows = await repo.get_multi(PdmFileSnapshotFilterDto(sync_state="ingested"))
        assert total == 1
        assert rows[0].file_id == 2

    async def test_filters_by_kind(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, kind="made"),
                _snapshot(file_id=2, kind="bought"),
            ]
        )
        await db.commit()

        total, rows = await repo.get_multi(PdmFileSnapshotFilterDto(kind="bought"))
        assert total == 1
        assert rows[0].file_id == 2

    async def test_search_matches_name_path_and_part_number(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, name="Housing.SLDPRT", part_number=None),
                _snapshot(file_id=2, name="Widget.SLDPRT", part_number="PN-HOUSING-1"),
                _snapshot(file_id=3, name="Other.SLDPRT", path="\\Bought-Parts\\Other.SLDPRT"),
            ]
        )
        await db.commit()

        _, by_name = await repo.get_multi(PdmFileSnapshotFilterDto(search="Housing"))
        assert {r.file_id for r in by_name} == {1, 2}

        _, by_path = await repo.get_multi(PdmFileSnapshotFilterDto(search="Bought-Parts"))
        assert {r.file_id for r in by_path} == {3}

    async def test_sorted_last_seen_at_desc_and_paged(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, last_seen_at=_NOW - timedelta(days=2)),
                _snapshot(file_id=2, last_seen_at=_NOW),
                _snapshot(file_id=3, last_seen_at=_NOW - timedelta(days=1)),
            ]
        )
        await db.commit()

        total, rows = await repo.get_multi(PdmFileSnapshotFilterDto())
        assert total == 3
        assert [r.file_id for r in rows] == [2, 3, 1]

        _, page = await repo.get_multi(PdmFileSnapshotFilterDto(skip=1, limit=1))
        assert [r.file_id for r in page] == [3]


class TestGetAllForVault:
    """The whole-vault load that PollPdmVault's walk diffs against. The poller
    does this once per run instead of querying per file."""

    async def test_returns_every_row_of_the_vault(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(file_id=1, path="\\Made-Parts\\A.SLDPRT"),
                _snapshot(file_id=2, path="\\Bought-Parts\\B.SLDPRT"),
            ]
        )
        await db.commit()

        rows = await repo.get_all_for_vault("V1")

        assert {r.file_id for r in rows} == {1, 2}

    async def test_scoped_to_one_vault(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(vault_id="V1", file_id=1),
                _snapshot(vault_id="V2", file_id=1),
            ]
        )
        await db.commit()

        rows = await repo.get_all_for_vault("V1")

        assert len(rows) == 1
        assert rows[0].vault_id == "V1"

    async def test_empty_vault_returns_an_empty_list(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)

        assert await repo.get_all_for_vault("V1") == []


class TestResetSkippedToPending:
    async def test_requeues_skipped_rows_for_the_vault_and_clears_the_error(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(
                    vault_id="V1",
                    file_id=1,
                    sync_state=PdmFileSyncState.SKIPPED,
                    last_error="stale reason",
                ),
                _snapshot(
                    vault_id="V1",
                    file_id=2,
                    sync_state=PdmFileSyncState.SKIPPED,
                    last_error="another reason",
                ),
                # Not skipped, so unaffected.
                _snapshot(vault_id="V1", file_id=3, sync_state=PdmFileSyncState.INGESTED),
                # Skipped, but for a different vault, so unaffected.
                _snapshot(
                    vault_id="V2",
                    file_id=4,
                    sync_state=PdmFileSyncState.SKIPPED,
                    last_error="reason",
                ),
            ]
        )
        await db.commit()

        count = await repo.reset_skipped_to_pending("V1")
        await db.commit()

        assert count == 2
        first = await repo.get_by_file("V1", 1)
        second = await repo.get_by_file("V1", 2)
        assert first is not None and first.sync_state == "pending" and first.last_error is None
        assert second is not None and second.sync_state == "pending" and second.last_error is None
        assert (await repo.get_by_file("V1", 3)).sync_state == "ingested"
        assert (await repo.get_by_file("V2", 4)).sync_state == "skipped"

    async def test_returns_zero_when_nothing_is_skipped(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [_snapshot(vault_id="V1", file_id=1, sync_state=PdmFileSyncState.INGESTED)]
        )
        await db.commit()

        assert await repo.reset_skipped_to_pending("V1") == 0


class TestListConflicts:
    async def test_returns_only_conflicts_for_the_vault(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(vault_id="V1", file_id=1, sync_state=PdmFileSyncState.CONFLICT),
                _snapshot(vault_id="V1", file_id=2, sync_state=PdmFileSyncState.INGESTED),
                _snapshot(vault_id="V2", file_id=3, sync_state=PdmFileSyncState.CONFLICT),
            ]
        )
        await db.commit()

        results = await repo.list_conflicts("V1")
        assert {r.file_id for r in results} == {1}


class TestCountsByState:
    async def test_groups_by_sync_state_for_the_vault(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many(
            [
                _snapshot(vault_id="V1", file_id=1, sync_state=PdmFileSyncState.PENDING),
                _snapshot(vault_id="V1", file_id=2, sync_state=PdmFileSyncState.PENDING),
                _snapshot(vault_id="V1", file_id=3, sync_state=PdmFileSyncState.INGESTED),
                _snapshot(vault_id="V2", file_id=4, sync_state=PdmFileSyncState.PENDING),
            ]
        )
        await db.commit()

        counts = await repo.counts_by_state("V1")
        assert counts == {"pending": 2, "ingested": 1}


class TestSave:
    async def test_creates_a_new_row(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(_snapshot(file_id=1))
        await db.commit()

        assert saved.id != 0
        assert await repo.get_by_id(saved.id) is not None

    async def test_updates_an_existing_row(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(_snapshot(file_id=1, sync_state=PdmFileSyncState.PENDING))
        await db.commit()

        changed = _snapshot(file_id=1, sync_state=PdmFileSyncState.INGESTED, item_id=42)
        changed.id = saved.id
        await repo.save(changed)
        await db.commit()

        result = await repo.get_by_id(saved.id)
        assert result is not None
        assert result.sync_state == "ingested"
        assert result.item_id == 42


class TestPerFolderQueries:
    async def test_get_by_file_ids_and_parent_folder_ids(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        rows = [_snapshot(file_id=i) for i in range(1, 6)]
        rows[4].parent_folder_id = 2
        await repo.upsert_many(rows)
        await repo.upsert_many([_snapshot(vault_id="V2", file_id=1)])
        await db.commit()

        by_file = await repo.get_by_file_ids("V1", [1, 3, 99])
        by_parent = await repo.get_by_parent_folder_ids("V1", [2])

        assert sorted(r.file_id for r in by_file) == [1, 3]
        assert [r.file_id for r in by_parent] == [5]

    async def test_upsert_many_updates_and_inserts_in_one_batch(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, version=1)])
        await db.commit()

        await repo.upsert_many([_snapshot(file_id=1, version=2), _snapshot(file_id=2)])
        await db.commit()

        assert (await repo.get_by_file("V1", 1)).version == 2
        assert await repo.get_by_file("V1", 2) is not None


class TestPreviewCandidates:
    async def test_only_unlinked_or_newer_rows_of_the_kind(self, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        unlinked = _snapshot(file_id=1, part_number="CAD-1")
        up_to_date = _snapshot(file_id=2, part_number="CAD-2", item_id=7, version=3)
        up_to_date.last_ingested_version = 3
        newer = _snapshot(file_id=3, part_number="CAD-3", item_id=8, version=4)
        newer.last_ingested_version = 3
        missing = _snapshot(file_id=4, part_number="CAD-4", sync_state=PdmFileSyncState.MISSING)
        other_kind = _snapshot(file_id=5, part_number="CAD-5", kind="bought")
        await repo.upsert_many([unlinked, up_to_date, newer, missing, other_kind])
        await db.commit()

        rows = await repo.get_preview_candidates("V1", "made")

        assert sorted(r.file_id for r in rows) == [1, 3]
