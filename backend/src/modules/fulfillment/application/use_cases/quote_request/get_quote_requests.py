"""
Reads quote requests, one or a page, each with its lines, suppliers and
offers compared, a request's changelog, and the open requests that ask for given demands or lot
positions, which the demand and lot tables mark as "in quotation".
"""

from src.modules.fulfillment.application.dto.quote_request_dto import OpenQuoteRequestLinksResult
from src.modules.fulfillment.application.dto.quote_request_dto import OpenQuoteRequestRefResult
from src.modules.fulfillment.application.dto.quote_request_dto import PaginatedQuoteRequests
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestResult
from src.modules.fulfillment.application.mappers.quote_request_mapper import QuoteRequestMapper
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.errors import QuoteRequestNotFoundError
from src.modules.fulfillment.domain.services.quote_request_rules import (
    allowed_quote_request_actions,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    IQuoteRequestRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    OpenQuoteRequestRef,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    QuoteRequestFilterDto,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class GetQuoteRequests:
    def __init__(self, request_repo: IQuoteRequestRepository) -> None:
        self._requests = request_repo

    async def get_one(self, actor: User, request_id: int) -> QuoteRequestResult:
        request = found_or_raise(
            await self._requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )
        return QuoteRequestMapper.to_result(request, allowed_quote_request_actions(request, actor))

    async def entity(self, request_id: int) -> QuoteRequest:
        return found_or_raise(
            await self._requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )

    async def changelog(self, request_id: int) -> list[str]:
        """The request's changelog lines; a missing id raises
        QuoteRequestNotFoundError, as get_one does."""
        return (await self.entity(request_id)).changes

    async def get_many(self, actor: User, filters: QuoteRequestFilterDto) -> PaginatedQuoteRequests:
        total, requests = await self._requests.get_multi(filters)
        return PaginatedQuoteRequests(
            total=total,
            items=[
                QuoteRequestMapper.to_result(r, allowed_quote_request_actions(r, actor))
                for r in requests
            ],
        )


def _refs(
    found: dict[int, list[OpenQuoteRequestRef]],
) -> dict[int, list[OpenQuoteRequestRefResult]]:
    return {
        key: [OpenQuoteRequestRefResult(id=r.id, request_number=r.request_number) for r in refs]
        for key, refs in found.items()
    }


class GetOpenQuoteRequestLinks:
    def __init__(self, request_repo: IQuoteRequestRepository) -> None:
        self._requests = request_repo

    async def execute(
        self,
        *,
        bought_demand_ids: list[int],
        source_demand_ids: list[int],
        lot_position_ids: list[int],
    ) -> OpenQuoteRequestLinksResult:
        links = await self._requests.get_open_links(
            bought_demand_ids=bought_demand_ids,
            source_demand_ids=source_demand_ids,
            lot_position_ids=lot_position_ids,
        )
        return OpenQuoteRequestLinksResult(
            bought_demands=_refs(links.bought_demands),
            source_demands=_refs(links.source_demands),
            lot_positions=_refs(links.lot_positions),
        )
