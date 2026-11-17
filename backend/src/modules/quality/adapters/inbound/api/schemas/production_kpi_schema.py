"""
HTTP schema for the production KPI query parameters, shared by every
/api/v1/web/production-kpi endpoint. The result bodies are the
application-layer DTOs in src.modules.quality.application.dto.production_kpi_dto
directly, they are already API-shaped and need no wire-format mirror.
"""

from datetime import date

from fastapi import Query
from pydantic import BaseModel
from pydantic import model_validator

from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.quality.application.dto.production_kpi_dto import KpiFilter


class ProductionKpiFilterParams(BaseModel):
    date_from: date = Query(...)
    date_to: date = Query(...)
    machine_id: int | None = Query(default=None)
    machine_pool_id: int | None = Query(default=None)
    project_id: int | None = Query(default=None)
    customer_id: int | None = Query(default=None)

    # A domain error, not a ValueError: these params are a Depends() model,
    # whose ValueError FastAPI would answer with a 500 instead of a 422.
    @model_validator(mode="after")
    def validate_filter(self) -> "ProductionKpiFilterParams":
        if self.date_to < self.date_from:
            raise InvalidInputError("date_to must not be before date_from.")
        if self.machine_id is not None and self.machine_pool_id is not None:
            raise InvalidInputError("machine_id and machine_pool_id are mutually exclusive.")
        return self

    def to_filter(self) -> KpiFilter:
        return KpiFilter(
            date_from=self.date_from,
            date_to=self.date_to,
            machine_id=self.machine_id,
            machine_pool_id=self.machine_pool_id,
            project_id=self.project_id,
            customer_id=self.customer_id,
        )
