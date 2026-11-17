"""
The background jobs of meetings: sending the bundled notifications whose
five minutes are up, removing stored files no meeting file names any more,
and purging meetings older than the retention period with their files.
The composition root runs them on intervals (src/bootstrap/workers/).
"""

from collections.abc import Mapping
from datetime import timedelta

from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.workspace.application.use_cases.meeting._file_kind import (
    MEETING_FILE_STORAGE_PREFIX,
)
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.domain.events.meeting_events import MeetingActivityDue
from src.modules.workspace.domain.services.meeting_rules import NOTIFICATION_DELAY
from src.modules.workspace.domain.services.meeting_rules import meeting_activity_message
from src.modules.workspace.domain.services.meeting_rules import meeting_activity_title
from src.modules.workspace.domain.value_objects.meeting_activity_phrases import (
    MeetingActivityPhrases,
)
from src.shared_kernel.domain.services.clock import now_utc

# A blob without a row is left alone this long, so an upload whose row is
# about to commit is never taken for an orphan.
ORPHAN_MIN_AGE = timedelta(hours=24)


class FlushMeetingNotifications:
    """Publishes one event per meeting and recipient whose mentions and todo
    assignments have waited their five minutes, and clears them, in one
    commit. The title and the sentence are written in the recipient's
    language from `phrases`, the words of every shipped language, since the
    in-app panel and the digest show them as they are. The notification
    rule turns each event into the in-app notification and the digest mail
    entry."""

    def __init__(
        self,
        ports: MeetingPorts,
        event_bus: IEventBus,
        phrases: Mapping[Language, MeetingActivityPhrases],
    ) -> None:
        self._ports = ports
        self._bus = event_bus
        self._phrases = phrases

    async def execute(self) -> int:
        due = await self._ports.queue.get_due(now_utc() - NOTIFICATION_DELAY)
        sent = 0
        for pending in due:
            meeting = await self._ports.meetings.get_by_id(pending.meeting_id)
            if meeting is not None and not meeting.deleted and not meeting.invalid:
                users = await self._ports.meetings.get_users(
                    {*pending.actor_ids, pending.recipient_id}
                )
                recipient = users.get(pending.recipient_id)
                language = recipient.language if recipient is not None else Language.default()
                phrases = self._phrases.get(language) or self._phrases[Language.default()]
                names = [
                    (users[a].full_name.split() or [users[a].username])[0]
                    for a in pending.actor_ids
                    if a in users
                ]
                await self._bus.publish(
                    MeetingActivityDue(
                        meeting_id=meeting.id,
                        meeting_number=meeting.meeting_number,
                        recipient_id=pending.recipient_id,
                        mention_count=pending.mention_count,
                        todo_count=pending.todo_count,
                        message=meeting_activity_message(
                            phrases,
                            names,
                            pending.mention_count,
                            pending.todo_count,
                            meeting.meeting_number,
                        ),
                        title=meeting_activity_title(phrases, meeting.meeting_number),
                    )
                )
                sent += 1
            await self._ports.queue.delete(pending)
        await self._ports.uow.commit()
        return sent


class SweepOrphanMeetingFiles:
    """Removes the blobs under the meeting files' storage prefix that are
    older than a day and that no file row names, and logs how many."""

    def __init__(self, ports: MeetingPorts) -> None:
        self._ports = ports

    async def execute(self) -> int:
        storage = self._ports.storage
        if storage is None:
            return 0
        cutoff = now_utc() - ORPHAN_MIN_AGE
        stale = [
            o.key
            for o in await storage.list_objects(f"{MEETING_FILE_STORAGE_PREFIX}/")
            if o.last_modified < cutoff
        ]
        known = await self._ports.files.get_known_storage_paths(stale)
        await self._ports.uow.commit()
        orphans = [key for key in stale if key not in known]
        for key in orphans:
            await delete_storage_object_best_effort(
                storage, key, context="sweeping unreferenced meeting files"
            )
        log.info(f"Meeting file sweep removed {len(orphans)} unreferenced blob(s).")
        return len(orphans)


class PurgeExpiredMeetings:
    """Purges the meetings that started longer ago than the retention
    period, each in a commit of its own, and removes their files once that
    commit has succeeded. Nothing happens while the period is 0."""

    def __init__(self, ports: MeetingPorts) -> None:
        self._ports = ports

    async def execute(self) -> int:
        days = (await self._ports.settings.get_retention()).meeting_retention_days
        if days <= 0:
            return 0
        expired = await self._ports.meetings.list_started_before(now_utc() - timedelta(days=days))
        for meeting_id in expired:
            await purge_meeting(self._ports, meeting_id)
        if expired:
            log.info(f"Purged {len(expired)} meeting(s) past the retention period.")
        return len(expired)


async def purge_meeting(ports: MeetingPorts, meeting_id: int) -> None:
    """Removes a meeting with every row that belongs to it, then its files
    from storage once that has committed. A failed blob delete leaves an
    orphan for the nightly sweep."""
    files = await ports.files.get_by_item_id(meeting_id)
    await ports.meetings.purge(meeting_id)
    await ports.uow.commit()
    if ports.storage is None:
        return
    for file in files:
        await delete_storage_object_best_effort(
            ports.storage, file.storage_path, context=f"purging meeting #{meeting_id}"
        )
