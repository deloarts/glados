"""Builds the use case factories for one family's demand bucket CRUD. The
bought-item, made-item and source-item families wire the same four use
cases the same way and differ only in their repository factory and use case
classes, so each family's deps module calls this once.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


@dataclass(frozen=True)
class DemandBucketUseCaseDeps:
    """The `Depends()` factories one family's bucket router reads."""

    get_buckets: Callable[..., Any]
    create: Callable[..., Any]
    update: Callable[..., Any]
    delete: Callable[..., Any]


def build_demand_bucket_deps(
    repo_dep: Callable[..., Any],
    *,
    get_buckets_cls: Callable[..., Any],
    create_cls: Callable[..., Any],
    update_cls: Callable[..., Any],
    delete_cls: Callable[..., Any],
) -> DemandBucketUseCaseDeps:
    def get_buckets_use_case(bucket_repo: Any = Depends(repo_dep)) -> Any:
        return get_buckets_cls(bucket_repo=bucket_repo)

    def get_create_bucket_use_case(
        bucket_repo: Any = Depends(repo_dep),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> Any:
        return create_cls(bucket_repo=bucket_repo, uow=uow)

    def get_update_bucket_use_case(
        bucket_repo: Any = Depends(repo_dep),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> Any:
        return update_cls(bucket_repo=bucket_repo, uow=uow)

    def get_delete_bucket_use_case(
        bucket_repo: Any = Depends(repo_dep),
        uow: IUnitOfWork = Depends(get_unit_of_work),
    ) -> Any:
        return delete_cls(bucket_repo=bucket_repo, uow=uow)

    return DemandBucketUseCaseDeps(
        get_buckets=get_buckets_use_case,
        create=get_create_bucket_use_case,
        update=get_update_bucket_use_case,
        delete=get_delete_bucket_use_case,
    )
