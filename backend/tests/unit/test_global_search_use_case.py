"""
Unit tests for GlobalSearch: the empty-query short-circuit (repo never
called), term stripping, dataclass -> pydantic mapping, and the
SEARCH_RESOURCES/LiveResource vocabulary staying in sync (the port module
cannot import LiveResource directly, see global_search_repository.py's
docstring). No database.
"""

from uuid import uuid4

from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.read.application.use_cases.search.global_search import GlobalSearch
from src.read.ports.outbound.repositories.global_search_repository import SEARCH_RESOURCES
from src.read.ports.outbound.repositories.global_search_repository import SearchGroup
from src.read.ports.outbound.repositories.global_search_repository import SearchHit
from src.read.ports.outbound.repositories.global_search_repository import SearchHitDetails
from tests.integration._sqlite_similarity import similarity


class FakeGlobalSearchRepository:
    def __init__(self, groups: list[SearchGroup] | None = None) -> None:
        self.groups = groups or []
        self.calls: list[tuple[str, int]] = []

    async def search(self, term: str, limit: int) -> list[SearchGroup]:
        self.calls.append((term, limit))
        return self.groups


def test_search_resources_match_the_live_resource_vocabulary():
    assert SEARCH_RESOURCES == (
        LiveResource.PRODUCTS,
        LiveResource.PROJECTS,
        LiveResource.BOUGHT_ITEMS,
        LiveResource.MADE_ITEMS,
        LiveResource.SOURCE_ITEMS,
        LiveResource.ORDERS,
        LiveResource.PRODUCTION_LOTS,
        LiveResource.PRODUCTION_ORDERS,
        LiveResource.CALCULATIONS,
        LiveResource.CHECKLISTS,
        LiveResource.MEETINGS,
    )


async def test_whitespace_only_query_returns_eight_empty_groups_without_calling_the_repo():
    repo = FakeGlobalSearchRepository()

    result = await GlobalSearch(repo).execute(query="   ", limit=5)

    assert repo.calls == []
    assert result.query == ""
    assert [g.resource for g in result.groups] == list(SEARCH_RESOURCES)
    assert all(g.total == 0 and g.items == [] for g in result.groups)


async def test_empty_query_returns_eight_empty_groups_without_calling_the_repo():
    repo = FakeGlobalSearchRepository()

    result = await GlobalSearch(repo).execute(query="", limit=5)

    assert repo.calls == []
    assert [g.resource for g in result.groups] == list(SEARCH_RESOURCES)


async def test_the_term_is_stripped_before_reaching_the_repo():
    repo = FakeGlobalSearchRepository()

    result = await GlobalSearch(repo).execute(query="  AX-22  ", limit=5)

    assert repo.calls == [("AX-22", 5)]
    assert result.query == "AX-22"


async def test_mapping_preserves_every_hit_field_and_the_group_total():
    public_id = uuid4()
    repo = FakeGlobalSearchRepository(
        groups=[
            SearchGroup(
                resource="projects",
                total=12,
                items=[
                    SearchHit(
                        resource="projects",
                        id=7,
                        public_id=public_id,
                        label="AX-2201",
                        subtitle="Injection mold housing",
                    )
                ],
            )
        ]
    )

    result = await GlobalSearch(repo).execute(query="AX-22", limit=5)

    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.resource == "projects"
    assert group.total == 12
    assert len(group.items) == 1
    hit = group.items[0]
    assert hit.resource == "projects"
    assert hit.id == 7
    assert hit.public_id == public_id
    assert hit.label == "AX-2201"
    assert hit.subtitle == "Injection mold housing"
    assert hit.match_kind == "contains"
    assert hit.via_kind is None


async def test_mapping_preserves_a_related_hits_match_kind_and_via_kind():
    repo = FakeGlobalSearchRepository(
        groups=[
            SearchGroup(
                resource="production-lots",
                total=1,
                items=[
                    SearchHit(
                        resource="production-lots",
                        id=1,
                        public_id=uuid4(),
                        label="LOT-1",
                        subtitle="planned",
                        match_kind="related",
                        via_kind="item",
                    )
                ],
            )
        ]
    )

    result = await GlobalSearch(repo).execute(query="TN-26-00004", limit=5)

    hit = result.groups[0].items[0]
    assert hit.match_kind == "related"
    assert hit.via_kind == "item"


async def test_mapping_preserves_a_fuzzy_hits_match_kind():
    repo = FakeGlobalSearchRepository(
        groups=[
            SearchGroup(
                resource="projects",
                total=0,
                items=[
                    SearchHit(
                        resource="projects",
                        id=1,
                        public_id=uuid4(),
                        label="AX-2201",
                        subtitle=None,
                        match_kind="fuzzy",
                    )
                ],
            )
        ]
    )

    result = await GlobalSearch(repo).execute(query="AX-2201-typo", limit=5)

    hit = result.groups[0].items[0]
    assert hit.match_kind == "fuzzy"
    assert hit.via_kind is None


async def test_mapping_preserves_a_null_subtitle():
    repo = FakeGlobalSearchRepository(
        groups=[
            SearchGroup(
                resource="orders",
                total=1,
                items=[
                    SearchHit(
                        resource="orders",
                        id=1,
                        public_id=uuid4(),
                        label="O-1",
                        subtitle=None,
                    )
                ],
            )
        ]
    )

    result = await GlobalSearch(repo).execute(query="O-1", limit=5)

    assert result.groups[0].items[0].subtitle is None


async def test_mapping_preserves_every_details_field_when_populated():
    repo = FakeGlobalSearchRepository(
        groups=[
            SearchGroup(
                resource="production-orders",
                total=1,
                items=[
                    SearchHit(
                        resource="production-orders",
                        id=1,
                        public_id=uuid4(),
                        label="PO-1",
                        subtitle="queued",
                        details=SearchHitDetails(
                            status="queued",
                            article_name="Housing",
                            part_number="TN-26-00004",
                            order_code_1="ABC-123",
                            revision="B",
                            item_count=3,
                            supplier_name="ACME",
                            made_item_id=12,
                            made_item_part_number="TN-...",
                            made_item_revision="B",
                            made_item_article_name="Housing",
                            source_label="Ø40 1.4301",
                            steps=["Sawing", "Milling"],
                            execution_kind="machine",
                            execution_label="DMU 50",
                        ),
                    )
                ],
            )
        ]
    )

    result = await GlobalSearch(repo).execute(query="PO-1", limit=5)

    details = result.groups[0].items[0].details
    assert details is not None
    assert details.status == "queued"
    assert details.article_name == "Housing"
    assert details.part_number == "TN-26-00004"
    assert details.order_code_1 == "ABC-123"
    assert details.revision == "B"
    assert details.item_count == 3
    assert details.supplier_name == "ACME"
    assert details.made_item_id == 12
    assert details.made_item_part_number == "TN-..."
    assert details.made_item_revision == "B"
    assert details.made_item_article_name == "Housing"
    assert details.source_label == "Ø40 1.4301"
    assert details.steps == ["Sawing", "Milling"]
    assert details.execution_kind == "machine"
    assert details.execution_label == "DMU 50"


async def test_mapping_preserves_a_null_details():
    repo = FakeGlobalSearchRepository(
        groups=[
            SearchGroup(
                resource="products",
                total=1,
                items=[
                    SearchHit(
                        resource="products",
                        id=1,
                        public_id=uuid4(),
                        label="P-1",
                        subtitle=None,
                    )
                ],
            )
        ]
    )

    result = await GlobalSearch(repo).execute(query="P-1", limit=5)

    assert result.groups[0].items[0].details is None


# ── The SQLite similarity() shim (tests/integration/_sqlite_similarity.py) ─
#
# Exercised here (not tests/integration) because it is a pure function with
# no database involved, see that module's docstring for what it
# approximates and why (pg_trgm's `similarity()`, registered on every
# SQLite DBAPI connection by tests/integration/conftest.py so the fuzzy
# fallback query runs the same way in the test suite as in production).


def test_similarity_of_identical_strings_is_one():
    assert similarity("TN-26-00004", "TN-26-00004") == 1.0


def test_similarity_of_disjoint_strings_is_zero():
    assert similarity("abc", "xyz") == 0.0


def test_similarity_of_a_typo_pair_clears_the_pg_trgm_default_threshold():
    # A single missing digit, the same kind of typo the fuzzy fallback
    # exists to tolerate (strict ILIKE substring matching would not find
    # "TN-26-00004" for a search of "TN-26-0004").
    assert similarity("TN-26-00004", "TN-26-0004") >= 0.3


def test_similarity_is_none_when_either_argument_is_none():
    # Mirrors pg_trgm's own NULL-in/NULL-out similarity(): a WHERE clause
    # comparing NULL to a threshold evaluates to NULL, excluding the row,
    # same as a real NULL column would.
    assert similarity(None, "abc") is None
    assert similarity("abc", None) is None
