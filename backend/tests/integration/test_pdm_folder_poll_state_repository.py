"""
DB-backed coverage for SqlAlchemyPdmFolderPollStateRepository: upsert
(insert then update in place), get_all_for_vault (keyed by folder_key,
scoped to the vault), and reset (clears an existing row, no-ops when none
exists).
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_folder_poll_state_repository import (
    SqlAlchemyPdmFolderPollStateRepository,
)
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState

_NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _state(
    *, vault_id: str = "V1", folder_key: str = "path:\\made-parts", **overrides: object
) -> PdmFolderPollState:
    defaults: dict[str, object] = dict(
        id=0,
        vault_id=vault_id,
        folder_key=folder_key,
        consecutive_unchanged_runs=0,
        next_due_at=None,
        last_changed_at=None,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return PdmFolderPollState(**defaults)  # type: ignore[arg-type]


class TestUpsert:
    async def test_inserts_a_new_row(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)

        await repo.upsert(
            _state(consecutive_unchanged_runs=2, next_due_at=_NOW + timedelta(hours=1))
        )
        await db.commit()

        states = await repo.get_all_for_vault("V1")
        assert set(states) == {"path:\\made-parts"}
        state = states["path:\\made-parts"]
        assert state.consecutive_unchanged_runs == 2
        assert state.next_due_at is not None

    async def test_updates_an_existing_row_in_place(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)
        await repo.upsert(_state(consecutive_unchanged_runs=1))
        await db.commit()

        await repo.upsert(
            _state(consecutive_unchanged_runs=4, next_due_at=_NOW + timedelta(hours=2))
        )
        await db.commit()

        states = await repo.get_all_for_vault("V1")
        assert len(states) == 1
        assert states["path:\\made-parts"].consecutive_unchanged_runs == 4

    async def test_does_not_commit_by_itself(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)

        await repo.upsert(_state())
        await db.rollback()

        assert await repo.get_all_for_vault("V1") == {}


class TestGetAllForVault:
    async def test_scoped_to_the_vault(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)
        await repo.upsert(_state(vault_id="V1", folder_key="path:\\a"))
        await repo.upsert(_state(vault_id="V2", folder_key="path:\\b"))
        await db.commit()

        states = await repo.get_all_for_vault("V1")

        assert set(states) == {"path:\\a"}

    async def test_empty_vault_returns_an_empty_dict(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)

        assert await repo.get_all_for_vault("V-none") == {}


class TestReset:
    async def test_clears_an_existing_row(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)
        await repo.upsert(
            _state(consecutive_unchanged_runs=5, next_due_at=_NOW + timedelta(hours=3))
        )
        await db.commit()

        await repo.reset("V1", "path:\\made-parts")
        await db.commit()

        state = (await repo.get_all_for_vault("V1"))["path:\\made-parts"]
        assert state.consecutive_unchanged_runs == 0
        assert state.next_due_at is None
        assert state.last_changed_at is not None

    async def test_noop_when_no_row_exists(self, db):
        repo = SqlAlchemyPdmFolderPollStateRepository(db)

        await repo.reset("V-none", "path:\\nowhere")
        await db.commit()

        assert await repo.get_all_for_vault("V-none") == {}
