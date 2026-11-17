"""
The contacts group of the global search: added after the other groups for
a reader of contacts, and never searched for anyone else. No database.
"""

from uuid import uuid4

from src.modules.platform.domain.value_objects.permission import Permission
from src.read.application.use_cases.search.global_search import GlobalSearch
from src.read.ports.outbound.repositories.global_search_repository import SEARCH_RESOURCES
from src.read.ports.outbound.repositories.global_search_repository import SearchGroup
from src.read.ports.outbound.repositories.global_search_repository import SearchHit
from tests.factories import make_user


class FakeSearchRepository:
    def __init__(self) -> None:
        self.contact_calls: list[tuple[str, int]] = []

    async def search(self, term: str, limit: int) -> list[SearchGroup]:
        return [SearchGroup(resource=resource, total=0, items=[]) for resource in SEARCH_RESOURCES]

    async def search_contacts(self, term: str, limit: int) -> SearchGroup:
        self.contact_calls.append((term, limit))
        hit = SearchHit(resource="contacts", id=1, public_id=uuid4(), label="Sabine", subtitle=None)
        return SearchGroup(resource="contacts", total=1, items=[hit])


async def test_a_reader_of_contacts_gets_the_contacts_group_last() -> None:
    repo = FakeSearchRepository()
    reader = make_user(permissions=[Permission.READ_CONTACTS])

    result = await GlobalSearch(repo).execute(query=" sabine ", limit=5, actor=reader)

    assert [g.resource for g in result.groups] == [*SEARCH_RESOURCES, "contacts"]
    assert result.groups[-1].items[0].label == "Sabine"
    assert repo.contact_calls == [("sabine", 5)]


async def test_anyone_else_never_searches_contacts() -> None:
    repo = FakeSearchRepository()

    result = await GlobalSearch(repo).execute(
        query="sabine", limit=5, actor=make_user(permissions=[])
    )

    assert [g.resource for g in result.groups] == list(SEARCH_RESOURCES)
    assert repo.contact_calls == []


async def test_a_blank_query_lists_an_empty_contacts_group_for_a_reader() -> None:
    repo = FakeSearchRepository()
    reader = make_user(permissions=[Permission.READ_CONTACTS])

    result = await GlobalSearch(repo).execute(query="  ", limit=5, actor=reader)

    assert [g.resource for g in result.groups] == [*SEARCH_RESOURCES, "contacts"]
    assert all(g.total == 0 for g in result.groups)
    assert repo.contact_calls == []
