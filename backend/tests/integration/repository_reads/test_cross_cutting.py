"""
Read scenarios that span aggregates: global search, printing,
notifications, acknowledgements, the part-number registry and the wall
displays. See the package docstring for how the scenarios work.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
    SqlAlchemyPartNumberRegistryRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.infoscreen_repository import (
    SqlAlchemyInfoscreenRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.terminal_broadcast_repository import (
    SqlAlchemyTerminalBroadcastRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.terminal_repository import (
    SqlAlchemyTerminalRepository,
)
from src.modules.operations.domain.entities.infoscreen import Infoscreen
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.entities.terminal_broadcast import TerminalBroadcast
from src.modules.operations.domain.value_objects.infoscreen import InfoscreenColorMode
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastSeverity
from src.modules.operations.domain.value_objects.terminal_broadcast import TerminalBroadcastStyle
from src.modules.platform.adapters.outbound.persistence.repositories.acknowledgement_repository import (
    SqlAlchemyAcknowledgementRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.email_notification_repository import (
    SqlAlchemyEmailNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.security_event_repository import (
    SqlAlchemySecurityEventRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_group_repository import (
    SqlAlchemyUserGroupRepository,
)
from src.modules.platform.domain.entities.acknowledgement import Acknowledgement
from src.modules.platform.domain.entities.api_key import ApiKey
from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.entities.notification import Notification
from src.modules.platform.domain.entities.security_event import make_security_event
from src.modules.platform.domain.entities.user_group import UserGroup
from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    SecurityEventFilterDto,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_job_repository import (
    SqlAlchemyPrintJobRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.ports.outbound.repositories.print_job_repository import PrintJobFilterDto
from src.read.adapters.outbound.persistence.repositories.global_search_repository import (
    SqlAlchemyGlobalSearchRepository,
)
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()


@SCENARIOS.register(SqlAlchemyGlobalSearchRepository)
async def _global_search(g: Graph, r: Any) -> None:
    """Every seeded number and name ends in "1", so one term hits every
    resource and each resource's detail loading runs."""
    await g.full_lot()
    await g.bought_order_item()
    await g.calculation()
    await g.checklist()
    await g.meeting()
    groups = await r.search("1", 10)
    empty = [group.resource for group in groups if not group.items]
    assert not empty, f"search hit nothing for {empty}, so their mappers never ran"
    # Contacts are a group of their own, which only a reader of contacts gets.
    assert (await r.search_contacts("1", 10)).items


@SCENARIOS.register(SqlAlchemyPrintTemplateRepository)
async def _print_templates(g: Graph, r: Any) -> None:
    template = await g.print_template()
    assert template.trigger is not None
    await r.get_all()
    await r.get_armed_by_trigger(template.trigger)
    await r.get_by_classifier(template.classifier)


@SCENARIOS.register(SqlAlchemyPrintJobRepository)
async def _print_jobs(g: Graph, r: Any) -> None:
    template = await g.print_template()
    lot = await g.lot()
    await SqlAlchemyPrintJobRepository(g.db).save(
        make(
            PrintJob,
            template_id=template.id,
            printer_id=template.printer_id,
            classifier=template.classifier,
            root_type=PrintRootType.PRODUCTION_LOT,
            root_id=lot.id,
            copies=1,
            status=PrintJobStatus.SENT,
            trigger=PrintJobTrigger.MANUAL,
            source_event_id="evt-1",
            actor_id=g.uid,
        )
    )
    await g.db.commit()
    await r.get_multi(PrintJobFilterDto())


@SCENARIOS.register(SqlAlchemyNotificationRepository)
async def _notifications(g: Graph, r: Any) -> None:
    notification = await SqlAlchemyNotificationRepository(g.db).save(
        make(
            Notification,
            user_id=g.uid,
            type=NotificationType.PROJECT_ASSIGNED,
            title="t",
            message="m",
            is_read=False,
            created_at=NOW,
        )
    )
    await g.db.commit()
    await r.maybe_empty.exists_by_source_event_id("none")
    await r.get_by_id(notification.id)
    await r.get_by_user_id(g.uid)
    await r.get_unread_count(g.uid)


@SCENARIOS.register(SqlAlchemyEmailNotificationRepository)
async def _email_notifications(g: Graph, r: Any) -> None:
    demand = await g.made_demand()
    await SqlAlchemyEmailNotificationRepository(g.db).save(
        make(EmailNotification, reason="delivered", receiver_id=g.uid, demand_item_id=demand.id)
    )
    await g.db.commit()
    await r.get_all()
    await r.get_by_receiver_id(g.uid)
    await r.get_distinct_receiver_ids()


@SCENARIOS.register(SqlAlchemyPartNumberRegistryRepository)
async def _part_number_registry(g: Graph, r: Any) -> None:
    repo = SqlAlchemyPartNumberRegistryRepository(g.db)
    await repo.claim("M-1", "made")
    await g.db.commit()
    await r.all_entries()
    await r.owner_of("M-1")
    # Plain columns, no mapper, and every item of the graph is registered.
    await r.maybe_empty.find_unregistered_holders()
    await r.next_part_number("M-{seq}")


@SCENARIOS.register(SqlAlchemyAcknowledgementRepository)
async def _acknowledgements(g: Graph, r: Any) -> None:
    ack = await SqlAlchemyAcknowledgementRepository(g.db).create(
        make(
            Acknowledgement,
            text="Read me",
            severity=AnnouncementSeverity.INFO,
            enabled=True,
            show_when=AcknowledgementShowWhen.IMMEDIATELY,
            created_at=NOW,
            created_by_id=g.uid,
        ),
        [g.uid, g.other_user.id],
    )
    await g.db.commit()
    await r.get_by_public_id(ack.public_id)
    await r.get_pending_for_user(g.uid, None)
    await r.list_recipients(ack.id)
    await r.list_summaries()


async def _wall_display(g: Graph) -> tuple[Infoscreen, Terminal, Terminal]:
    """A screen, an approved terminal showing it with every link set, and a
    terminal still waiting to be paired."""
    api_key = await SqlAlchemyApiKeyRepository(g.db).save(
        make(
            ApiKey,
            name="Terminal key",
            token_hash="0" * 64,
            token_prefix="gt_",
            user_id=g.other_user.id,
            permissions=["connect:terminals"],
            created_by_id=g.uid,
            created=NOW,
        )
    )
    screen = await SqlAlchemyInfoscreenRepository(g.db).save(
        make(
            Infoscreen,
            created=NOW,
            name="Hall 1",
            color_mode=InfoscreenColorMode.DARK,
            rotation_seconds=30,
            creator_id=g.uid,
        )
    )
    terminals = SqlAlchemyTerminalRepository(g.db)
    approved = await terminals.save(
        make(
            Terminal,
            public_key="approved-key",
            public_key_fingerprint="0" * 16,
            status=TerminalStatus.APPROVED,
            mode=TerminalMode.INFOSCREEN,
            infoscreen_id=screen.id,
            api_key_id=api_key.id,
            approved_at=NOW,
            approved_by_id=g.uid,
            created=NOW,
        )
    )
    pending = await terminals.save(
        make(
            Terminal,
            public_key="pending-key",
            public_key_fingerprint="1" * 16,
            status=TerminalStatus.PENDING,
            mode=TerminalMode.INFOSCREEN,
            pairing_code="123456",
            pairing_expires_at=NOW + timedelta(minutes=10),
            api_key_id=api_key.id,
            created=NOW,
        )
    )
    await g.db.commit()
    return screen, approved, pending


@SCENARIOS.register(SqlAlchemyTerminalRepository)
async def _terminals(g: Graph, r: Any) -> None:
    _, approved, _ = await _wall_display(g)
    await r.get_by_id(approved.id)
    await r.get_by_public_key(approved.public_key)
    await r.get_visible(NOW)
    await r.get_all()
    await r.get_by_status(TerminalStatus.APPROVED)
    assert await r.count_active_pending(NOW) == 1
    assert await r.get_pending_pairing_codes() == {"123456"}


@SCENARIOS.register(SqlAlchemyTerminalBroadcastRepository)
async def _terminal_broadcasts(g: Graph, r: Any) -> None:
    screen, approved, _ = await _wall_display(g)
    broadcast = await r.save(
        make(
            TerminalBroadcast,
            created=NOW,
            text="Fire drill at noon",
            severity=TerminalBroadcastSeverity.WARNING,
            style=TerminalBroadcastStyle.BANNER,
            show_until=NOW + timedelta(hours=1),
            all_terminals=False,
            created_by_id=g.uid,
            terminal_ids=(approved.id,),
            infoscreen_ids=(screen.id,),
        )
    )
    await g.db.commit()
    await r.get_by_id(broadcast.id)
    assert [b.id for b in await r.get_active(NOW)] == [broadcast.id]


@SCENARIOS.register(SqlAlchemyUserGroupRepository)
async def _user_groups(g: Graph, r: Any) -> None:
    group = await r.save(
        make(
            UserGroup,
            created=NOW,
            changes=[],
            name="Shift leads",
            permissions=[],
            creator_id=g.uid,
            member_ids=[g.uid],
            changed_by_id=g.uid,
        )
    )
    await g.db.commit()
    await r.list_all()
    await r.get_by_id(group.id)
    assert (await r.get_by_name_ci("shift LEADS")).id == group.id


@SCENARIOS.register(SqlAlchemySecurityEventRepository)
async def _security_events(g: Graph, r: Any) -> None:
    await SqlAlchemySecurityEventRepository(g.db).append(
        make_security_event(
            SecurityEventType.LOGIN,
            outcome=SecurityEventOutcome.SUCCESS,
            actor_user_id=g.uid,
            actor_username="u",
            target_user_id=g.uid,
            target_username="u",
        )
    )
    await g.db.commit()
    total, events = await r.list_page(
        SecurityEventFilterDto(
            event_type=SecurityEventType.LOGIN,
            outcome=SecurityEventOutcome.SUCCESS,
            user_id=g.uid,
            occurred_from=NOW.date(),
            occurred_to=NOW.date(),
        )
    )
    assert total == len(events) == 1


@SCENARIOS.register(SqlAlchemyInfoscreenRepository)
async def _infoscreens(g: Graph, r: Any) -> None:
    screen, _, _ = await _wall_display(g)
    await r.get_by_id(screen.id)
    await r.get_all(include_archived=False)
    await r.get_live_by_name(screen.name)
    # No default saved yet still maps to a default that is always on.
    await r.get_display_default()


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
