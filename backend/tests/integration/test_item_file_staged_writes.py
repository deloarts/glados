"""
The no-commit file-row writes PDM document sync stages before its single
commit: the row is visible inside the transaction, gone after a rollback
and kept after a commit.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
    BoughtItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_file_repository import (
    SqlAlchemyBoughtItemFileRepository,
)
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from tests.integration.test_api_file_downloads import _bought_item


def _file(item_id: int, name: str) -> BoughtItemFile:
    return BoughtItemFile(
        id=0,
        bought_item_id=item_id,
        file_name=f"{name}.pdf",
        stored_name=f"{name}.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path=f"bought_items/{item_id}/pdf/{name}.pdf",
        sha256="x",
        category=BoughtItemFileCategory.PDF,
        created=datetime.now(UTC),
        uploaded_by_user_id=1,
    )


async def _count(db, item_id: int) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(BoughtItemFileOrmModel)
        .where(BoughtItemFileOrmModel.bought_item_id == item_id)
    )


async def test_a_staged_row_is_gone_after_a_rollback(db, create_user) -> None:
    await create_user()
    item = await _bought_item(db, id_suffix="stage1")
    repo = SqlAlchemyBoughtItemFileRepository(db)

    staged = await repo.save(_file(item.id, "rolled-back"))
    assert staged.id > 0
    assert await _count(db, item.id) == 1

    await db.rollback()

    assert await _count(db, item.id) == 0


async def test_a_staged_row_and_a_staged_delete_land_together_on_commit(db, create_user) -> None:
    await create_user()
    item = await _bought_item(db, id_suffix="stage2")
    repo = SqlAlchemyBoughtItemFileRepository(db)
    old = await repo.save(_file(item.id, "old"))

    new = await repo.save(_file(item.id, "new"))
    await repo.delete(old)
    await db.commit()

    remaining = await repo.get_by_item_id(item.id)
    assert [f.id for f in remaining] == [new.id]
