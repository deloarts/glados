"""
Unit tests for made-item demand bucket use cases (CRUD) and
SetDemandItemBucket. No database, no HTTP. All dependencies replaced
with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    CreateMadeItemDemandBucketCommand,
)
from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    UpdateMadeItemDemandBucketCommand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.set_demand_item_bucket import (
    SetDemandItemBucket,
)
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket.create_bucket import (
    CreateBucket,
)
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket.delete_bucket import (
    DeleteBucket,
)
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket.get_bucket import (
    GetBucket,
)
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket.get_bucket import (
    GetBuckets,
)
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket.update_bucket import (
    UpdateBucket,
)
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import MadeItemDemandBucketAlreadyExistsError
from src.modules.fulfillment.domain.errors import MadeItemDemandBucketNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    MadeItemDemandBucketFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_bucket(
    id: int = 1,
    name: str = "Urgent",
    color: str = "#ff0000",
) -> MadeItemDemandBucket:
    return MadeItemDemandBucket(
        id=id,
        created=date(2026, 1, 1),
        name=name,
        color=color,
        creator_id=1,
    )


def make_demand(
    id: int = 1,
    bucket_id: int | None = None,
) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=MadeItemDemandStatus.OPEN,
        quantity=5.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        bucket_id=bucket_id,
    )


class FakeBucketRepository:
    def __init__(self, buckets: list[MadeItemDemandBucket] | None = None):
        self._buckets: dict[int, MadeItemDemandBucket] = {}
        self._next_id = 1
        for b in buckets or []:
            self._buckets[b.id] = b
            self._next_id = max(self._next_id, b.id + 1)
        self.deleted_ids: list[int] = []

    async def get_by_id(self, id: int) -> MadeItemDemandBucket | None:
        return self._buckets.get(id)

    async def get_by_name(self, name: str) -> MadeItemDemandBucket | None:
        return next(
            (b for b in self._buckets.values() if b.name.lower() == name.lower()),
            None,
        )

    async def get_multi(
        self, filters: MadeItemDemandBucketFilterDto
    ) -> tuple[int, list[MadeItemDemandBucket]]:
        results = list(self._buckets.values())
        if filters.search:
            results = [b for b in results if filters.search.lower() in b.name.lower()]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def save(self, bucket: MadeItemDemandBucket) -> MadeItemDemandBucket:
        if bucket.id == 0:
            bucket.id = self._next_id
            self._next_id += 1
        self._buckets[bucket.id] = bucket
        return bucket

    async def delete(self, bucket: MadeItemDemandBucket) -> None:
        self.deleted_ids.append(bucket.id)
        self._buckets.pop(bucket.id, None)


class FakeDemandRepository:
    def __init__(self, demands: list[MadeItemDemandItem] | None = None):
        self._demands: dict[int, MadeItemDemandItem] = {}
        for d in demands or []:
            self._demands[d.id] = d

    async def get_by_id(self, id: int) -> MadeItemDemandItem | None:
        return self._demands.get(id)

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem:
        self._demands[demand.id] = demand
        return demand


# ── CreateBucket ──────────────────────────────────────────────────────


class TestCreateBucket:
    def setup_method(self):
        self.repo = FakeBucketRepository()
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.use_case = CreateBucket(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> CreateMadeItemDemandBucketCommand:
        defaults = dict(name="Urgent", color="#ff0000")
        defaults.update(kwargs)
        return CreateMadeItemDemandBucketCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "Urgent"
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_name_raises(self):
        await self.repo.save(make_bucket(name="Urgent"))
        with pytest.raises(MadeItemDemandBucketAlreadyExistsError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(name="Urgent"))

    async def test_duplicate_name_is_case_insensitive(self):
        await self.repo.save(make_bucket(name="Urgent"))
        with pytest.raises(MadeItemDemandBucketAlreadyExistsError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(name="URGENT"))

    async def test_name_is_stripped(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(name="  Urgent  "))
        assert result.name == "Urgent"

    async def test_invalid_color_raises(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(color="red"))

    async def test_creator_id_is_set(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_DEMAND_ITEMS])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 7


# ── UpdateBucket ──────────────────────────────────────────────────────


class TestUpdateBucket:
    def setup_method(self):
        self.bucket = make_bucket(id=1, name="Urgent")
        self.repo = FakeBucketRepository([self.bucket])
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.use_case = UpdateBucket(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateMadeItemDemandBucketCommand:
        defaults = dict(name="Urgent", color="#00ff00")
        defaults.update(kwargs)
        return UpdateMadeItemDemandBucketCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, bucket_id=1, cmd=self._cmd(name="Later")
        )
        assert result.name == "Later"
        assert result.color == "#00ff00"

    async def test_not_found_raises(self):
        with pytest.raises(MadeItemDemandBucketNotFoundError):
            await self.use_case.execute(actor=self.actor, bucket_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, bucket_id=1, cmd=self._cmd())

    async def test_changing_to_existing_name_raises(self):
        await self.repo.save(make_bucket(id=2, name="Later"))
        with pytest.raises(MadeItemDemandBucketAlreadyExistsError):
            await self.use_case.execute(actor=self.actor, bucket_id=1, cmd=self._cmd(name="Later"))

    async def test_keeping_same_name_does_not_raise(self):
        result = await self.use_case.execute(
            actor=self.actor, bucket_id=1, cmd=self._cmd(name="Urgent")
        )
        assert result.name == "Urgent"

    async def test_invalid_color_raises(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, bucket_id=1, cmd=self._cmd(color="not-a-color")
            )


# ── DeleteBucket ──────────────────────────────────────────────────────


class TestDeleteBucket:
    def setup_method(self):
        self.bucket = make_bucket(id=1)
        self.repo = FakeBucketRepository([self.bucket])
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.use_case = DeleteBucket(self.repo, uow=FakeUnitOfWork())

    async def test_deletes_successfully(self):
        result = await self.use_case.execute(actor=self.actor, bucket_id=1)
        assert result.id == 1
        assert await self.repo.get_by_id(1) is None
        assert self.repo.deleted_ids == [1]

    async def test_not_found_raises(self):
        with pytest.raises(MadeItemDemandBucketNotFoundError):
            await self.use_case.execute(actor=self.actor, bucket_id=999)

    async def test_unprivileged_cannot_delete(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, bucket_id=1)


# ── GetBucket / GetBuckets ────────────────────────────────────────────


class TestGetBucket:
    def setup_method(self):
        self.buckets = [
            make_bucket(id=1, name="Alpha"),
            make_bucket(id=2, name="Beta"),
        ]
        self.repo = FakeBucketRepository(self.buckets)

    async def test_get_existing(self):
        result = await GetBucket(self.repo).execute(bucket_id=1)
        assert result.name == "Alpha"

    async def test_get_nonexistent_raises(self):
        with pytest.raises(MadeItemDemandBucketNotFoundError):
            await GetBucket(self.repo).execute(bucket_id=999)

    async def test_get_all(self):
        result = await GetBuckets(self.repo).execute(filters=MadeItemDemandBucketFilterDto())
        assert result.total == 2

    async def test_search_filters_by_name(self):
        result = await GetBuckets(self.repo).execute(
            filters=MadeItemDemandBucketFilterDto(search="alp")
        )
        assert result.total == 1
        assert result.items[0].name == "Alpha"


# ── SetDemandItemBucket ───────────────────────────────────────────────


class TestSetDemandItemBucket:
    def setup_method(self):
        self.bucket = make_bucket(id=1)
        self.demand = make_demand(id=1)
        self.bucket_repo = FakeBucketRepository([self.bucket])
        self.demand_repo = FakeDemandRepository([self.demand])
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.use_case = SetDemandItemBucket(
            self.demand_repo, self.bucket_repo, uow=FakeUnitOfWork()
        )

    async def test_assigns_bucket(self):
        result = await self.use_case.execute(actor=self.actor, demand_id=1, bucket_id=1)
        assert result.bucket_id == 1

    async def test_clears_bucket(self):
        self.demand.bucket_id = 1
        result = await self.use_case.execute(actor=self.actor, demand_id=1, bucket_id=None)
        assert result.bucket_id is None

    async def test_reassigning_the_same_bucket_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, demand_id=1, bucket_id=1)
        result = await self.use_case.execute(actor=self.actor, demand_id=1, bucket_id=1)
        assert result.bucket_id == 1

    async def test_demand_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(actor=self.actor, demand_id=999, bucket_id=1)

    async def test_bucket_not_found_raises(self):
        with pytest.raises(MadeItemDemandBucketNotFoundError):
            await self.use_case.execute(actor=self.actor, demand_id=1, bucket_id=999)

    async def test_unprivileged_cannot_assign(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, demand_id=1, bucket_id=1)

    async def test_does_not_touch_changed_or_changes(self):
        before_changed = self.demand.changed
        before_changes = list(self.demand.changes)
        await self.use_case.execute(actor=self.actor, demand_id=1, bucket_id=1)
        assert self.demand.changed == before_changed
        assert self.demand.changes == before_changes
