"""
DB-backed coverage for LabeledCatalogueRepositoryBase, run through each of
its four concrete subclasses: the insert and update round trip, the missing
row error, the archived handling of get_live_names, get_multi and
get_aggregate, and the list filter, search and sort over the language maps
the names and descriptions are stored as.
"""

from typing import Any

import pytest

from src.modules.catalogue.adapters.outbound.persistence.repositories.article_group_repository import (
    SqlAlchemyArticleGroupRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    InspectionMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    SourceItemTypeFilterDto,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.integration.repository_reads._graph import make

FAMILIES = [
    pytest.param(
        SqlAlchemyArticleGroupRepository, ArticleGroup, ArticleGroupFilterDto, id="article_group"
    ),
    pytest.param(
        SqlAlchemySourceItemTypeRepository,
        SourceItemType,
        SourceItemTypeFilterDto,
        id="source_item_type",
    ),
    pytest.param(
        SqlAlchemyFabricationMethodRepository,
        FabricationMethod,
        FabricationMethodFilterDto,
        id="fabrication_method",
    ),
    pytest.param(
        SqlAlchemyInspectionMethodRepository,
        InspectionMethod,
        InspectionMethodFilterDto,
        id="inspection_method",
    ),
]


def _en(text: str) -> LocalizedText:
    return LocalizedText({"enGB": text})


def _names(items: list[Any]) -> list[str]:
    return [i.name.values["enGB"] for i in items]


async def _seed(repo: Any, entity_cls: type, uid: int) -> list[Any]:
    """Three rows; Alpha alone carries a second language, whose text sorts
    after every other name so a sort in that language is visible."""
    rows = [
        make(
            entity_cls,
            name=LocalizedText({"enGB": "Alpha", "deAT": "Zulu (deAT)"}),
            description=_en("first"),
            creator_id=uid,
        ),
        make(entity_cls, name=_en("Beta"), description=_en("needle inside"), creator_id=uid),
        make(
            entity_cls, name=_en("Gamma"), description=_en("third"), creator_id=uid, archived=True
        ),
    ]
    return [await repo.save(row) for row in rows]


@pytest.mark.parametrize(("repo_cls", "entity_cls", "filter_cls"), FAMILIES)
class TestLabeledCatalogueRepository:
    async def test_labeled_catalogue_save_inserts_then_updates(
        self, db, create_user, repo_cls, entity_cls, filter_cls
    ):
        user = await create_user()
        repo = repo_cls(db)
        saved = await repo.save(make(entity_cls, name=_en("Alpha"), creator_id=user.id))
        assert saved.id > 0
        assert saved.creator is not None
        assert saved.creator.id == user.id

        saved.description = LocalizedText({"enGB": "changed", "deAT": "changed (deAT)"})
        updated = await repo.save(saved)
        assert updated.id == saved.id
        assert updated.description == saved.description
        await db.commit()

        reread = await repo_cls(db).get_by_id(saved.id)
        assert reread is not None
        assert reread.name == _en("Alpha")
        assert reread.description.as_dict() == {"enGB": "changed", "deAT": "changed (deAT)"}

    async def test_labeled_catalogue_save_of_a_missing_row_raises(
        self, db, create_user, repo_cls, entity_cls, filter_cls
    ):
        user = await create_user()
        with pytest.raises(ValueError, match=rf"{repo_cls._model.__name__} id=999999 not found\."):
            await repo_cls(db).save(make(entity_cls, id=999999, name=_en("X"), creator_id=user.id))

    async def test_labeled_catalogue_get_live_names_skips_archived_rows(
        self, db, create_user, repo_cls, entity_cls, filter_cls
    ):
        user = await create_user()
        repo = repo_cls(db)
        alpha, beta, _gamma = await _seed(repo, entity_cls, user.id)
        live = sorted(await repo.get_live_names(), key=lambda row: row[0])
        assert live == [
            (alpha.id, LocalizedText({"enGB": "Alpha", "deAT": "Zulu (deAT)"})),
            (beta.id, _en("Beta")),
        ]

    async def test_labeled_catalogue_get_multi_filters_searches_and_sorts(
        self, db, create_user, repo_cls, entity_cls, filter_cls
    ):
        user = await create_user()
        repo = repo_cls(db)
        await _seed(repo, entity_cls, user.id)
        # The web routes always pass the viewer's label languages, so the
        # name sort is checked in English and, further down, in deAT.
        en = ("enGB",)

        total, items = await repo.get_multi(filter_cls(order_by="name", languages=en))
        assert total == 2
        assert _names(items) == ["Alpha", "Beta"]

        total, items = await repo.get_multi(
            filter_cls(include_archived=True, order_by="name", order_dir="desc", languages=en)
        )
        assert total == 3
        assert _names(items) == ["Gamma", "Beta", "Alpha"]

        total, items = await repo.get_multi(filter_cls(search="NEEDLE"))
        assert (total, _names(items)) == (1, ["Beta"])

        total, items = await repo.get_multi(filter_cls(name="alp"))
        assert (total, _names(items)) == (1, ["Alpha"])

        total, items = await repo.get_multi(filter_cls(name="zulu"))
        assert (total, _names(items)) == (1, ["Alpha"])

        total, items = await repo.get_multi(filter_cls(order_by="name", languages=("deAT",)))
        assert (total, _names(items)) == (2, ["Beta", "Alpha"])

        total, items = await repo.get_multi(
            filter_cls(include_archived=True, skip=1, limit=1, order_by="name", languages=en)
        )
        assert total == 3
        assert _names(items) == ["Beta"]

    async def test_labeled_catalogue_get_aggregate_counts_archived_rows(
        self, db, create_user, repo_cls, entity_cls, filter_cls
    ):
        user = await create_user()
        repo = repo_cls(db)
        assert await repo.get_aggregate() == (0, None)
        await _seed(repo, entity_cls, user.id)
        count, max_changed = await repo.get_aggregate()
        assert count == 3
        assert max_changed is not None

    async def test_labeled_catalogue_delete_removes_the_row(
        self, db, create_user, repo_cls, entity_cls, filter_cls
    ):
        user = await create_user()
        repo = repo_cls(db)
        alpha, *_ = await _seed(repo, entity_cls, user.id)
        await repo.delete(alpha)
        assert await repo.get_by_id(alpha.id) is None
