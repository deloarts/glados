"""SQLAlchemy repository for the files of meetings, a subclass of the shared
item file repository with the meeting as the item and the card a pasted
image belongs to."""

from typing import Any

from sqlalchemy import select

from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingFileOrmModel,
)
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory


class SqlAlchemyMeetingFileRepository(SqlAlchemyItemFileRepository[MeetingFile]):
    _model = MeetingFileOrmModel
    _entity_cls = MeetingFile
    _category_cls = MeetingFileCategory
    _fk_field = "meeting_id"

    def _orm_to_entity(self, orm: Any) -> MeetingFile:
        entity = super()._orm_to_entity(orm)
        entity.card_id = orm.card_id
        return entity

    def _new_orm(self, file: MeetingFile) -> Any:
        orm = super()._new_orm(file)
        orm.card_id = file.card_id
        return orm

    async def get_known_storage_paths(self, paths: list[str]) -> set[str]:
        known: set[str] = set()
        # In chunks, so a large sweep stays below the bound parameter limit.
        for start in range(0, len(paths), 500):
            chunk = paths[start : start + 500]
            rows = await self._db.scalars(
                select(MeetingFileOrmModel.storage_path).where(
                    MeetingFileOrmModel.storage_path.in_(chunk)
                )
            )
            known.update(rows.all())
        return known
