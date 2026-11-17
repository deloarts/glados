"""
Shared route-building for the bought-item, made-item and source-item demand
bucket endpoints: list, create, update and delete under the family's bucket
prefix. Each family's endpoint module shrinks to one
`DemandBucketEndpointConfig` and a call here. Handler names, parameter names
and response models are the same for every family, so router.py's
include_router() prefix and tags registrations still mount the same paths
and operation ids as before.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.demand_buckets import DemandBucketUseCaseDeps
from src.modules.fulfillment.adapters.inbound.api.schemas.demand_bucket_schema import (
    DemandBucketCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.demand_bucket_schema import (
    DemandBucketFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.demand_bucket_schema import (
    DemandBucketResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.demand_bucket_schema import (
    DemandBucketUpdateRequest,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import CreateDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import DeleteDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBuckets
from src.modules.fulfillment.application.services.demand_bucket_crud import UpdateDemandBucket
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User


@dataclass(frozen=True)
class DemandBucketEndpointConfig:
    """One family's wiring: its filter DTO and command classes and its
    `deps/*_demand_buckets.py` use case factories."""

    filter_dto: Callable[..., Any]
    create_command: Callable[..., Any]
    update_command: Callable[..., Any]
    deps: DemandBucketUseCaseDeps


def build_demand_bucket_router(cfg: DemandBucketEndpointConfig) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_model=PageResponse[DemandBucketResponse])
    async def read_buckets(
        params: DemandBucketFilterParams = Depends(),
        _: User = Depends(get_current_active_user),
        use_case: GetDemandBuckets[Any, Any, Any] = Depends(cfg.deps.get_buckets),
    ) -> PageResponse[DemandBucketResponse]:
        result = await use_case.execute(params.to_dto(cfg.filter_dto))
        return PageResponse.from_result(result, params, item_model=DemandBucketResponse)

    @router.post("/", response_model=DemandBucketResponse, status_code=status.HTTP_201_CREATED)
    async def create_bucket(
        body: DemandBucketCreateRequest,
        actor: User = Depends(get_current_active_user),
        use_case: CreateDemandBucket[Any, Any] = Depends(cfg.deps.create),
    ) -> DemandBucketResponse:
        cmd = cfg.create_command(**body.model_dump())
        result = await use_case.execute(actor=actor, cmd=cmd)
        return DemandBucketResponse.model_validate(result.model_dump())

    @router.put("/{bucket_id}", response_model=DemandBucketResponse)
    async def update_bucket(
        bucket_id: int,
        body: DemandBucketUpdateRequest,
        actor: User = Depends(get_current_active_user),
        use_case: UpdateDemandBucket[Any, Any] = Depends(cfg.deps.update),
    ) -> DemandBucketResponse:
        cmd = cfg.update_command(**body.model_dump())
        result = await use_case.execute(actor=actor, bucket_id=bucket_id, cmd=cmd)
        return DemandBucketResponse.model_validate(result.model_dump())

    @router.delete("/{bucket_id}", response_model=DemandBucketResponse)
    async def delete_bucket(
        bucket_id: int,
        actor: User = Depends(get_current_active_user),
        use_case: DeleteDemandBucket[Any, Any] = Depends(cfg.deps.delete),
    ) -> DemandBucketResponse:
        result = await use_case.execute(actor=actor, bucket_id=bucket_id)
        return DemandBucketResponse.model_validate(result.model_dump())

    return router
