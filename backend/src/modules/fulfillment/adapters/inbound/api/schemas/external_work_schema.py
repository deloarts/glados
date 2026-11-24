"""Query parameters of the procurement list of external work. The rows are
returned as the use case's result models."""

from datetime import date

from fastapi import Query

from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkQuery
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkAlert
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkStage
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams


class ExternalWorkFilterParams(PageParams):
    search: str | None = Query(default=None, description="Lot, part number, article or project")
    fabrication_method_id: int | None = Query(default=None)
    supplier_id: int | None = Query(
        default=None,
        description="The line's supplier, or without a line the method's default supplier",
    )
    part: str | None = Query(default=None, description="Part number or article name")
    lot_ids: list[int] | None = Query(default=None, max_length=200)
    project_ids: list[int] | None = Query(default=None, max_length=200)
    product_ids: list[int] | None = Query(default=None, max_length=200)
    stages: list[ExternalWorkStage] | None = Query(default=None)
    alerts: list[ExternalWorkAlert] | None = Query(default=None)
    ready_from: date | None = Query(default=None)
    ready_to: date | None = Query(default=None)
    latest_pickup_from: date | None = Query(default=None)
    latest_pickup_to: date | None = Query(default=None)
    back_by_from: date | None = Query(default=None)
    back_by_to: date | None = Query(default=None)
    only_with_supplier: bool = Query(
        default=False, description="Only positions already on a supplier's order"
    )
    only_critical: bool = Query(
        default=False,
        description="Only positions not ready by their latest pickup, or overdue",
    )

    def to_query(self) -> ExternalWorkQuery:
        return ExternalWorkQuery(**self.model_dump())
