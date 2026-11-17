"""
Unit tests for the shared archive/restore helper
(src/modules/platform/application/services/archive_restore.py), covering idempotency (both
directions), the not-found path, and that `before_save` runs with the
entity's pre-flip `archived` value before the flag is actually flipped and
before the entity is persisted.
"""

from dataclasses import dataclass

import pytest

from src.modules.platform.application.services.archive_restore import set_archived


@dataclass
class _Widget:
    id: int
    archived: bool
    name: str = "widget"


class _NotFound(Exception):
    pass


class _FakeRepo:
    def __init__(self, widget: _Widget | None) -> None:
        self._widget = widget
        self.saved: list[_Widget] = []

    async def get_by_id(self, entity_id: int) -> _Widget | None:
        if self._widget is not None and self._widget.id == entity_id:
            return self._widget
        return None

    async def save(self, widget: _Widget) -> _Widget:
        self.saved.append(widget)
        return widget


class TestSetArchivedNotFound:
    async def test_raises_the_supplied_not_found_error_when_entity_missing(self):
        repo = _FakeRepo(widget=None)

        with pytest.raises(_NotFound):
            await set_archived(
                entity_id=999,
                archived=True,
                load=repo.get_by_id,
                not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
                save=repo.save,
            )

    async def test_does_not_save_when_entity_missing(self):
        repo = _FakeRepo(widget=None)

        with pytest.raises(_NotFound):
            await set_archived(
                entity_id=999,
                archived=True,
                load=repo.get_by_id,
                not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
                save=repo.save,
            )

        assert repo.saved == []


class TestSetArchivedIdempotency:
    async def test_archiving_an_already_archived_entity_is_not_an_error(self):
        widget = _Widget(id=1, archived=True)
        repo = _FakeRepo(widget=widget)

        result = await set_archived(
            entity_id=1,
            archived=True,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
        )

        assert result.archived is True
        assert repo.saved == [widget]

    async def test_restoring_an_already_live_entity_is_not_an_error(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)

        result = await set_archived(
            entity_id=1,
            archived=False,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
        )

        assert result.archived is False
        assert repo.saved == [widget]

    async def test_flips_from_live_to_archived(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)

        result = await set_archived(
            entity_id=1,
            archived=True,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
        )

        assert result.archived is True

    async def test_flips_from_archived_to_live(self):
        widget = _Widget(id=1, archived=True)
        repo = _FakeRepo(widget=widget)

        result = await set_archived(
            entity_id=1,
            archived=False,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
        )

        assert result.archived is False


class TestSetArchivedBeforeSaveOrdering:
    async def test_before_save_sees_the_pre_flip_archived_value(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)
        seen: list[bool] = []

        async def _before_save(entity: _Widget) -> None:
            seen.append(entity.archived)

        await set_archived(
            entity_id=1,
            archived=True,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
            before_save=_before_save,
        )

        assert seen == [False]

    async def test_before_save_runs_before_save_is_called(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)
        order: list[str] = []

        async def _before_save(entity: _Widget) -> None:
            order.append("before_save")

        async def _save(entity: _Widget) -> _Widget:
            order.append("save")
            return await repo.save(entity)

        await set_archived(
            entity_id=1,
            archived=True,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=_save,
            before_save=_before_save,
        )

        assert order == ["before_save", "save"]

    async def test_before_save_mutation_is_persisted(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)

        async def _before_save(entity: _Widget) -> None:
            entity.name = "renamed"

        result = await set_archived(
            entity_id=1,
            archived=True,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
            before_save=_before_save,
        )

        assert result.name == "renamed"

    async def test_before_save_raising_prevents_the_flip_and_the_save(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)

        class _Conflict(Exception):
            pass

        async def _before_save(entity: _Widget) -> None:
            raise _Conflict("guard failed")

        with pytest.raises(_Conflict):
            await set_archived(
                entity_id=1,
                archived=True,
                load=repo.get_by_id,
                not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
                save=repo.save,
                before_save=_before_save,
            )

        assert widget.archived is False
        assert repo.saved == []

    async def test_before_save_is_optional(self):
        widget = _Widget(id=1, archived=False)
        repo = _FakeRepo(widget=widget)

        result = await set_archived(
            entity_id=1,
            archived=True,
            load=repo.get_by_id,
            not_found=lambda eid: _NotFound(f"Widget #{eid} not found."),
            save=repo.save,
        )

        assert result.archived is True
