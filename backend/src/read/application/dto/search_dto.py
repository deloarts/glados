"""
Search result DTOs (hits, groups, global results with matching details).
"""

from uuid import UUID

from src.modules.platform.application.dto.base import ResultModel
from src.read.ports.outbound.repositories.global_search_repository import SearchMatchKind
from src.read.ports.outbound.repositories.global_search_repository import SearchResource
from src.read.ports.outbound.repositories.global_search_repository import SearchViaKind


class SearchHitDetails(ResultModel):
    status: str | None = None
    article_name: str | None = None
    part_number: str | None = None
    order_code_1: str | None = None
    revision: str | None = None
    item_count: int | None = None
    supplier_name: str | None = None
    made_item_id: int | None = None
    made_item_part_number: str | None = None
    made_item_revision: str | None = None
    made_item_article_name: str | None = None
    source_label: str | None = None
    steps: list[str] | None = None
    execution_kind: str | None = None
    execution_label: str | None = None


class SearchHitResult(ResultModel):
    resource: SearchResource
    id: int
    public_id: UUID
    label: str
    subtitle: str | None
    details: SearchHitDetails | None = None
    match_kind: SearchMatchKind = "contains"
    via_kind: SearchViaKind | None = None


class SearchGroupResult(ResultModel):
    resource: SearchResource
    total: int
    items: list[SearchHitResult]


class GlobalSearchResult(ResultModel):
    query: str
    groups: list[SearchGroupResult]
