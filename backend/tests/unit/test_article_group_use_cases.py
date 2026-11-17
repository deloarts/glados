"""
Unit tests for all article group use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.article_group_dto import CreateArticleGroupCommand
from src.modules.catalogue.application.dto.article_group_dto import UpdateArticleGroupCommand
from src.modules.catalogue.application.use_cases.article_group.archive_article_group import (
    ArchiveArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.create_article_group import (
    CreateArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroups,
)
from src.modules.catalogue.application.use_cases.article_group.restore_article_group import (
    RestoreArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.update_article_group import (
    UpdateArticleGroup,
)
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import LabelTranslationConflictError
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit._tenant_settings import TenantSettings
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_article_group(
    id: int = 1,
    name: str = "Bolts",
    archived: bool = False,
) -> ArticleGroup:
    return ArticleGroup(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        name=LocalizedText({"enGB": name}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
    )


class FakeArticleGroupRepository:
    def __init__(self, groups: list[ArticleGroup] | None = None):
        self._groups: dict[int, ArticleGroup] = {}
        self._next_id = 1
        for g in groups or []:
            self._groups[g.id] = g
            self._next_id = max(self._next_id, g.id + 1)

    async def get_by_id(self, id: int) -> ArticleGroup | None:
        return self._groups.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        return [(g.id, g.name) for g in self._groups.values() if not g.archived]

    async def get_by_ids(self, ids: list[int]) -> list[ArticleGroup]:
        return [g for g in self._groups.values() if g.id in ids]

    async def get_multi(self, filters: ArticleGroupFilterDto) -> tuple[int, list[ArticleGroup]]:
        results = list(self._groups.values())
        if filters.name:
            results = [
                g
                for g in results
                if any(filters.name.lower() in text.lower() for text in g.name.values.values())
            ]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def next_sort_order(self) -> int:
        return max((row.sort_order for row in self._groups.values()), default=-1) + 1

    async def save(self, article_group: ArticleGroup) -> ArticleGroup:
        if article_group.id == 0:
            article_group.id = self._next_id
            self._next_id += 1
        self._groups[article_group.id] = article_group
        return article_group

    async def delete(self, article_group: ArticleGroup) -> None:
        raise NotImplementedError


# ── CreateArticleGroup ────────────────────────────────────────────────


class TestCreateArticleGroup:
    def setup_method(self):
        self.repo = FakeArticleGroupRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ARTICLE_GROUPS])
        self.use_case = CreateArticleGroup(
            self.repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> CreateArticleGroupCommand:
        defaults = dict(name={"enGB": "Fasteners"})
        defaults.update(kwargs)
        return CreateArticleGroupCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == {"enGB": "Fasteners"}
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_name_raises(self):
        await self.repo.save(make_article_group(name="Fasteners"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(name={"enGB": "Fasteners"}))

    async def test_defaults_are_preserved(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.label_color == "#999999"
        assert result.label_font_color == "#000000"
        assert result.description == {}

    async def test_creator_id_is_set(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_ARTICLE_GROUPS])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 7


# ── UpdateArticleGroup ────────────────────────────────────────────────


class TestUpdateArticleGroup:
    def setup_method(self):
        self.group = make_article_group(id=1, name="Bolts")
        self.repo = FakeArticleGroupRepository([self.group])
        self.actor = make_user(permissions=[Permission.WRITE_ARTICLE_GROUPS])
        self.use_case = UpdateArticleGroup(
            self.repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> UpdateArticleGroupCommand:
        defaults = dict(
            name={"enGB": "Bolts"},
            label_color="#111111",
            label_font_color="#ffffff",
            description={"enGB": "Updated"},
        )
        defaults.update(kwargs)
        return UpdateArticleGroupCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, article_group_id=1, cmd=self._cmd(name={"enGB": "Screws"})
        )
        assert result.name == {"enGB": "Screws"}

    async def test_not_found_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await self.use_case.execute(actor=self.actor, article_group_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, article_group_id=1, cmd=self._cmd())

    async def test_changing_to_existing_name_raises(self):
        await self.repo.save(make_article_group(id=2, name="Screws"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(
                actor=self.actor, article_group_id=1, cmd=self._cmd(name={"enGB": "Screws"})
            )

    async def test_keeping_same_name_does_not_raise(self):
        result = await self.use_case.execute(
            actor=self.actor, article_group_id=1, cmd=self._cmd(name={"enGB": "Bolts"})
        )
        assert result.name == {"enGB": "Bolts"}


# ── ArchiveArticleGroup / RestoreArticleGroup ───────────────────────────


class TestArchiveArticleGroup:
    def setup_method(self):
        self.group = make_article_group(id=1)
        self.repo = FakeArticleGroupRepository([self.group])
        self.actor = make_user(permissions=[Permission.WRITE_ARTICLE_GROUPS])
        self.use_case = ArchiveArticleGroup(self.repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, article_group_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, article_group_id=1)
        result = await self.use_case.execute(actor=self.actor, article_group_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await self.use_case.execute(actor=self.actor, article_group_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, article_group_id=1)


class TestRestoreArticleGroup:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ARTICLE_GROUPS])

    async def test_restores_successfully(self):
        group = make_article_group(id=1, archived=True)
        repo = FakeArticleGroupRepository([group])
        result = await RestoreArticleGroup(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, article_group_id=1
        )
        assert result.archived is False

    async def test_restore_conflicts_when_name_already_taken_by_a_live_group(self):
        archived = make_article_group(id=1, name="Bolts", archived=True)
        live = make_article_group(id=2, name="Bolts", archived=False)
        repo = FakeArticleGroupRepository([archived, live])
        with pytest.raises(LabelTranslationConflictError):
            await RestoreArticleGroup(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, article_group_id=1
            )

    async def test_not_found_raises(self):
        repo = FakeArticleGroupRepository([])
        with pytest.raises(ArticleGroupNotFoundError):
            await RestoreArticleGroup(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, article_group_id=999
            )


# ── GetArticleGroup / GetArticleGroups ────────────────────────────────


class TestGetArticleGroup:
    def setup_method(self):
        self.groups = [
            make_article_group(id=1, name="Alpha"),
            make_article_group(id=2, name="Beta"),
            make_article_group(id=3, name="Gamma"),
        ]
        self.repo = FakeArticleGroupRepository(self.groups)

    async def test_get_existing(self):
        result = await GetArticleGroup(self.repo).execute(article_group_id=1)
        assert result.name == {"enGB": "Alpha"}

    async def test_get_nonexistent_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await GetArticleGroup(self.repo).execute(article_group_id=999)

    async def test_get_all(self):
        result = await GetArticleGroups(self.repo).execute(filters=ArticleGroupFilterDto())
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_with_limit(self):
        result = await GetArticleGroups(self.repo).execute(filters=ArticleGroupFilterDto(limit=1))
        assert len(result.items) == 1

    async def test_get_with_name_filter(self):
        result = await GetArticleGroups(self.repo).execute(
            filters=ArticleGroupFilterDto(name="beta")
        )
        assert result.total == 1
        assert result.items[0].name == {"enGB": "Beta"}
