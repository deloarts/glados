"""
The files of a meeting on the shared attachment base: list, upload,
download, rename and delete them. An image pasted into a card names the
card. Upload stores the blob before the row commits and removes it again
when the commit fails; delete commits first and removes the blob after.
Writing needs write:meetings and a meeting that is not invalid; reading
needs a signed-in user, like the meeting.
"""

from typing import Any

from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase
from src.modules.platform.application.services.file_attachments.base import GetItemFilesBase
from src.modules.platform.application.services.file_attachments.base import UpdateItemFileBase
from src.modules.platform.application.services.file_attachments.base import UploadItemFileBase
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.workspace.application.dto.meeting_dto import MeetingFileResult
from src.modules.workspace.application.dto.meeting_dto import RenameMeetingFileCommand
from src.modules.workspace.application.use_cases.meeting._file_kind import MEETING_FILE_KIND
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting._support import file_result
from src.modules.workspace.application.use_cases.meeting._support import load_card
from src.modules.workspace.application.use_cases.meeting._support import load_meeting
from src.modules.workspace.application.use_cases.meeting._support import record
from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.errors import MeetingFileNotFoundError
from src.modules.workspace.domain.errors import MeetingNotFoundError
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory


class GetMeetingFiles(GetItemFilesBase[MeetingFile, MeetingFileResult]):
    _kind = MEETING_FILE_KIND

    def __init__(self, ports: MeetingPorts) -> None:
        super().__init__(ports.meetings, ports.files, ports.storage)
        self._ports = ports

    async def execute(self, item_id: int) -> list[MeetingFileResult]:
        await load_meeting(self._ports, item_id)
        files = await self._ports.files.get_by_item_id(item_id)
        return [file_result(self._storage, f) for f in files]


class UploadMeetingFile(UploadItemFileBase[MeetingFile, MeetingFileResult]):
    _kind = MEETING_FILE_KIND

    def __init__(self, ports: MeetingPorts) -> None:
        super().__init__(ports.meetings, ports.files, ports.storage, uow=ports.uow)
        self._ports = ports

    async def _assert_editable(self, item: Any) -> None:
        meeting: Meeting = item
        if meeting.deleted:
            raise MeetingNotFoundError(f"Meeting #{meeting.id} not found.")
        MeetingRules.assert_editable(meeting)

    async def execute(
        self,
        actor: User,
        meeting_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: MeetingFileCategory,
        card_id: int | None = None,
    ) -> MeetingFileResult:
        if card_id is not None:
            MeetingRules.assert_can_write(actor)
            await load_card(self._ports, await load_meeting(self._ports, meeting_id), card_id)
        record_ = await self._store_blob(actor, meeting_id, data, file_name, content_type, category)
        record_.card_id = card_id
        storage = self._storage
        assert storage is not None  # _store_blob refuses to run without storage
        try:
            saved = await self._ports.files.save(record_)
            await record(
                self._ports,
                meeting_id,
                MeetingEventKind.FILE_ADDED,
                actor,
                card_id=card_id,
                file_id=saved.id,
                summary=saved.file_name,
            )
            await self._uow.commit()
        except Exception:
            await delete_storage_object_best_effort(
                storage,
                record_.storage_path,
                context=f"discarding unsaved file for meeting #{meeting_id}",
            )
            raise
        log.info(
            "File uploaded for meeting #%s: %r (%s, %s bytes) by user #%s.",
            meeting_id,
            file_name,
            saved.mime_type,
            saved.size_bytes,
            actor.id,
        )
        return file_result(storage, saved)


class RenameMeetingFile(UpdateItemFileBase[MeetingFile, MeetingFileResult]):
    _kind = MEETING_FILE_KIND

    def __init__(self, ports: MeetingPorts) -> None:
        super().__init__(ports.files, ports.storage, uow=ports.uow)
        self._ports = ports

    async def _assert_editable(self, file: Any) -> None:
        MeetingRules.assert_editable(await load_meeting(self._ports, file.meeting_id))

    async def rename(
        self, actor: User, meeting_id: int, file_id: int, file_name: str
    ) -> MeetingFileResult:
        file = await self._ports.files.get_by_id(file_id)
        if file is None or file.meeting_id != meeting_id:
            raise MeetingFileNotFoundError(f"File #{file_id} not found.")
        result = await self.execute(actor, file_id, RenameMeetingFileCommand(file_name=file_name))
        saved = await self._ports.files.get_by_id(file_id)
        assert saved is not None
        return result.model_copy(update={"card_id": saved.card_id})


class DeleteMeetingFile:
    """Removes the file's row and, once that has committed, its blob. An
    image a card's text still shows stays in the text as plain alt text the
    next time the card is saved."""

    def __init__(self, ports: MeetingPorts) -> None:
        self._ports = ports

    async def execute(self, actor: User, meeting_id: int, file_id: int) -> None:
        MeetingRules.assert_can_write(actor)
        meeting = await load_meeting(self._ports, meeting_id)
        MeetingRules.assert_editable(meeting)
        file = await self._ports.files.get_by_id(file_id)
        if file is None or file.meeting_id != meeting.id:
            raise MeetingFileNotFoundError(f"File #{file_id} not found.")
        await self._ports.files.delete(file)
        await record(
            self._ports,
            meeting.id,
            MeetingEventKind.FILE_DELETED,
            actor,
            file_id=file.id,
            summary=file.file_name,
        )
        await self._ports.uow.commit()
        # The blob goes only once the row deletion has committed, so a failed
        # commit leaves the row with its file intact.
        if self._ports.storage is not None:
            await delete_storage_object_best_effort(
                self._ports.storage, file.storage_path, context=f"deleting meeting file #{file_id}"
            )
        log.info("Meeting file #%s (%r) deleted.", file_id, file.file_name)


class DownloadMeetingFile(DownloadItemFileBase[MeetingFile]):
    _kind = MEETING_FILE_KIND

    def __init__(self, ports: MeetingPorts) -> None:
        super().__init__(ports.files, ports.storage, ports.uow)
        self._ports = ports

    async def execute(self, item_id: int, file_id: int) -> tuple[MeetingFile, bytes, str]:
        await load_meeting(self._ports, item_id)
        return await super().execute(item_id, file_id)
