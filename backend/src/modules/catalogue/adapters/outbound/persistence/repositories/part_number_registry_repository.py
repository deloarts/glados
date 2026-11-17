"""
Concrete SQLAlchemy implementation of IPartNumberRegistry
(docs/FIELD_OWNERSHIP.md principle 2, the made-item revision
rework). Like every repository write, none of these methods commit; the
caller's own unit of work covers the surrounding write.

Every write reads the registry row FOR UPDATE first. A release counts the
items still carrying the number before it deletes the row, and a revision
that keeps the number checks the row before it saves the item, so without
the lock a release could count no holder, the revision could find the row
and save its item, and the release could then delete the row the revision
relies on. Under the lock the second of the two waits: a release that comes
second counts the revision's committed item and keeps the row, and a
revision that comes second finds the row gone and claims it again.
"""

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.part_number_registry_model import (
    PartNumberRegistryOrmModel,
)
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.entities.part_number_registry import UnregisteredPartNumber
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.shared_kernel.domain.services.clock import now_utc


class SqlAlchemyPartNumberRegistryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get(
        self, part_number: str, *, lock: bool = False
    ) -> PartNumberRegistryOrmModel | None:
        statement = (
            select(PartNumberRegistryOrmModel)
            .where(PartNumberRegistryOrmModel.part_number == part_number)
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        row: PartNumberRegistryOrmModel | None = await self._db.scalar(statement)
        return row

    async def owner_of(self, part_number: str) -> PartNumberRegistryEntry | None:
        row = await self._get(part_number)
        if row is None:
            return None
        return PartNumberRegistryEntry(
            part_number=row.part_number, kind=ItemKind(row.kind), created=utc_aware(row.created)
        )

    async def claim(self, part_number: str, kind: str) -> None:
        existing = await self._get(part_number, lock=True)
        if existing is not None:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing.kind!r}."
            )
        self._db.add(
            PartNumberRegistryOrmModel(part_number=part_number, kind=kind, created=now_utc())
        )
        await self._db.flush()

    async def assert_family(self, part_number: str, kind: str) -> None:
        existing = await self._get(part_number, lock=True)
        if existing is None:
            await self.claim(part_number, kind)
            return
        if existing.kind != kind:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing.kind!r}."
            )

    async def release_if_unused(self, part_number: str) -> None:
        if await self._get(part_number, lock=True) is None:
            return
        # Soft-deleted rows still carry the number: no `deleted` filter
        # here, unlike almost every other lookup in these catalogues.
        still_made = (
            await self._db.scalar(
                select(MadeItemOrmModel.id)
                .where(MadeItemOrmModel.part_number == part_number)
                .limit(1)
            )
            is not None
        )
        if still_made:
            return
        still_bought = (
            await self._db.scalar(
                select(BoughtItemOrmModel.id)
                .where(BoughtItemOrmModel.part_number == part_number)
                .limit(1)
            )
            is not None
        )
        if still_bought:
            return
        await self._db.execute(
            delete(PartNumberRegistryOrmModel).where(
                PartNumberRegistryOrmModel.part_number == part_number
            )
        )
        await self._db.flush()

    async def all_entries(self) -> list[PartNumberRegistryEntry]:
        rows = (await self._db.scalars(select(PartNumberRegistryOrmModel))).all()
        return [
            PartNumberRegistryEntry(
                part_number=r.part_number, kind=ItemKind(r.kind), created=utc_aware(r.created)
            )
            for r in rows
        ]

    async def find_unregistered_holders(self) -> list[UnregisteredPartNumber]:
        found: dict[tuple[str, ItemKind], UnregisteredPartNumber] = {}
        for model, kind in (
            (MadeItemOrmModel, ItemKind.MADE),
            (BoughtItemOrmModel, ItemKind.BOUGHT),
        ):
            rows = await self._db.execute(
                select(
                    model.id, model.public_id, model.part_number, PartNumberRegistryOrmModel.kind
                )
                .outerjoin(
                    PartNumberRegistryOrmModel,
                    PartNumberRegistryOrmModel.part_number == model.part_number,
                )
                .where(model.part_number.is_not(None))
                .where(
                    (PartNumberRegistryOrmModel.part_number.is_(None))
                    | (PartNumberRegistryOrmModel.kind != kind.value)
                )
                .order_by(model.id)
            )
            for item_id, public_id, part_number, registered in rows:
                found.setdefault(
                    (part_number, kind),
                    UnregisteredPartNumber(
                        part_number=part_number,
                        kind=kind,
                        registered_kind=ItemKind(registered) if registered is not None else None,
                        item_id=item_id,
                        item_public_id=public_id,
                    ),
                )
        return [found[key] for key in sorted(found)]

    async def next_part_number(self, template: str) -> str:
        """Draws the next part number for `template` from the part counter
        (persistence/number_counters.py), started after the highest number in
        this registry rather than in the made or bought item table, so a
        shared numbering format yields one sequence across both kinds. A
        drawn number is never drawn again, even when its item is never
        saved, so a part number is never reused; one claimed by hand or by
        PDM in between makes the claim fail, and the caller draws again."""
        return await draw_number(
            self._db,
            NumberFamily.PART,
            template,
            column=PartNumberRegistryOrmModel.part_number,
        )
