"""
Runs a single search term across every searchable resource and returns the results grouped by
resource. A blank query short-circuits to an empty group per resource instead of querying the
repository. Contacts are personal data, so their group is added only for an actor who may read
contacts.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.read.application.dto.search_dto import GlobalSearchResult
from src.read.application.dto.search_dto import SearchGroupResult
from src.read.application.dto.search_dto import SearchHitDetails
from src.read.application.dto.search_dto import SearchHitResult
from src.read.ports.outbound.repositories.global_search_repository import CONTACT_SEARCH_RESOURCE
from src.read.ports.outbound.repositories.global_search_repository import SEARCH_RESOURCES
from src.read.ports.outbound.repositories.global_search_repository import IGlobalSearchRepository


class GlobalSearch:
    def __init__(self, repo: IGlobalSearchRepository) -> None:
        self._repo = repo

    async def execute(
        self, query: str, limit: int, actor: User | None = None
    ) -> GlobalSearchResult:
        """`actor`, when given, adds the groups its permissions open."""
        term = query.strip()
        with_contacts = actor is not None and actor.has_permission(Permission.READ_CONTACTS)
        if not term:
            resources = [*SEARCH_RESOURCES, *([CONTACT_SEARCH_RESOURCE] if with_contacts else [])]
            return GlobalSearchResult(
                query=term,
                groups=[
                    SearchGroupResult(resource=resource, total=0, items=[])
                    for resource in resources
                ],
            )
        groups = await self._repo.search(term, limit)
        if with_contacts:
            groups = [*groups, await self._repo.search_contacts(term, limit)]
        return GlobalSearchResult(
            query=term,
            groups=[
                SearchGroupResult(
                    resource=group.resource,
                    total=group.total,
                    items=[
                        SearchHitResult(
                            resource=hit.resource,
                            id=hit.id,
                            public_id=hit.public_id,
                            label=hit.label,
                            subtitle=hit.subtitle,
                            match_kind=hit.match_kind,
                            via_kind=hit.via_kind,
                            details=(
                                SearchHitDetails(
                                    status=hit.details.status,
                                    article_name=hit.details.article_name,
                                    part_number=hit.details.part_number,
                                    order_code_1=hit.details.order_code_1,
                                    revision=hit.details.revision,
                                    item_count=hit.details.item_count,
                                    supplier_name=hit.details.supplier_name,
                                    made_item_id=hit.details.made_item_id,
                                    made_item_part_number=hit.details.made_item_part_number,
                                    made_item_revision=hit.details.made_item_revision,
                                    made_item_article_name=hit.details.made_item_article_name,
                                    source_label=hit.details.source_label,
                                    steps=hit.details.steps,
                                    execution_kind=hit.details.execution_kind,
                                    execution_label=hit.details.execution_label,
                                )
                                if hit.details is not None
                                else None
                            ),
                        )
                        for hit in group.items
                    ],
                )
                for group in groups
            ],
        )
