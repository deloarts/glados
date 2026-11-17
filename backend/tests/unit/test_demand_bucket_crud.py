"""
Unit tests for the pieces the bought-item, made-item and source-item demand
bucket verticals share: the domain rules, the generic use cases driven by a
spec, and the shared filter params. The per-family test modules cover each
family's wiring end to end; these check that the shared code takes its
types and errors from the spec rather than from any one family.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date

import pytest

from src.modules.fulfillment.adapters.inbound.api.schemas.demand_bucket_schema import (
    DemandBucketFilterParams,
)
from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketCommandBase
from src.modules.fulfillment.application.services.demand_bucket_crud import CreateDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import DeleteDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import DemandBucketSpec
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBuckets
from src.modules.fulfillment.application.services.demand_bucket_crud import UpdateDemandBucket
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork


@dataclass
class _Bucket:
    id: int
    created: date
    name: str
    color: str
    creator_id: int


@dataclass
class _Result:
    id: int
    name: str


@dataclass
class _Filter:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None


class _NotFound(Exception):
    pass


class _AlreadyExists(Exception):
    pass


@dataclass
class _Repo:
    buckets: dict[int, _Bucket] = field(default_factory=dict)
    deleted: list[int] = field(default_factory=list)

    async def get_by_id(self, id: int) -> _Bucket | None:
        return self.buckets.get(id)

    async def get_by_name(self, name: str) -> _Bucket | None:
        return next((b for b in self.buckets.values() if b.name.lower() == name.lower()), None)

    async def get_multi(self, filters: _Filter) -> tuple[int, list[_Bucket]]:
        return len(self.buckets), list(self.buckets.values())

    async def save(self, bucket: _Bucket) -> _Bucket:
        if bucket.id == 0:
            bucket.id = max(self.buckets, default=0) + 1
        self.buckets[bucket.id] = bucket
        return bucket

    async def delete(self, bucket: _Bucket) -> None:
        self.deleted.append(bucket.id)
        self.buckets.pop(bucket.id, None)


_SPEC: DemandBucketSpec[_Bucket, _Result] = DemandBucketSpec(
    entity_cls=_Bucket,
    to_result=lambda b: _Result(id=b.id, name=b.name),
    not_found_error=_NotFound,
    already_exists_error=_AlreadyExists,
)


class _Create(CreateDemandBucket[_Bucket, _Result]):
    _spec = _SPEC


class _Update(UpdateDemandBucket[_Bucket, _Result]):
    _spec = _SPEC


class _Delete(DeleteDemandBucket[_Bucket, _Result]):
    _spec = _SPEC


class _GetMany(GetDemandBuckets[_Bucket, _Result, _Filter]):
    _spec = _SPEC


def _writer():
    return make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])


def _cmd(name: str = "Urgent", color: str = "#ff0000") -> DemandBucketCommandBase:
    return DemandBucketCommandBase(name=name, color=color)


async def test_demand_bucket_create_uses_spec_entity_result_and_commits(glados_caplog):
    repo, uow = _Repo(), FakeUnitOfWork()

    result = await _Create(repo, uow=uow).execute(actor=_writer(), cmd=_cmd(name="  Urgent "))

    assert result == _Result(id=1, name="Urgent")
    assert isinstance(repo.buckets[1], _Bucket)
    assert uow.commits == 1
    assert "Created bucket 'Urgent', ID=1." in glados_caplog.messages


async def test_demand_bucket_create_raises_spec_already_exists_error():
    repo = _Repo({1: _Bucket(1, date(2026, 1, 1), "Urgent", "#ff0000", 1)})

    with pytest.raises(_AlreadyExists, match=r"^A bucket named 'urgent' already exists\.$"):
        await _Create(repo, uow=FakeUnitOfWork()).execute(actor=_writer(), cmd=_cmd("urgent"))


async def test_demand_bucket_update_and_delete_raise_spec_not_found_error():
    with pytest.raises(_NotFound, match=r"^Bucket #7 not found\.$"):
        await _Update(_Repo(), uow=FakeUnitOfWork()).execute(
            actor=_writer(), bucket_id=7, cmd=_cmd()
        )
    with pytest.raises(_NotFound, match=r"^Bucket #7 not found\.$"):
        await _Delete(_Repo(), uow=FakeUnitOfWork()).execute(actor=_writer(), bucket_id=7)


async def test_demand_bucket_write_checks_permission_before_any_lookup():
    with pytest.raises(InsufficientPermissionsError):
        await _Delete(_Repo(), uow=FakeUnitOfWork()).execute(actor=make_user(), bucket_id=7)


async def test_demand_bucket_list_maps_every_row_through_the_spec():
    repo = _Repo({1: _Bucket(1, date(2026, 1, 1), "Urgent", "#ff0000", 1)})

    page = await _GetMany(repo).execute(filters=_Filter())

    assert page.total == 1
    assert page.items == [_Result(id=1, name="Urgent")]


def test_demand_bucket_filter_params_build_the_given_filter_dto():
    params = DemandBucketFilterParams(skip=5, limit=10, search="urg")

    assert params.to_dto(_Filter) == _Filter(skip=5, limit=10, search="urg")
