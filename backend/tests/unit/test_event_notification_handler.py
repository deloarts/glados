"""
Unit tests for HandleEventNotifications, the consumer that turns domain
events into in-app notifications and email digest entries. Covers the
notify-whom rules, which live here rather than in the use cases.

The "Event mail" section near the bottom covers account_deactivated/
permissions_changed/project_assigned/product_assigned, which also fire an
immediate system mail. `make_handler` (the helper every test above the
"Event mail" section uses) constructs HandleEventNotifications with just
the two positional repos, so mail sending stays off (see
HandleEventNotifications._mail_enabled) and those tests exercise only the
in-app/email-digest behaviour. `make_handler_with_mail` is the helper for
the mail-specific tests.
"""

from types import SimpleNamespace

from src.modules.catalogue.domain.events.bought_item_events import BoughtItemCreated
from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.events.order_events import OrderCanceled
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    HandleEventNotifications,
)
from src.modules.platform.domain.events.user_events import UserDeactivated
from src.modules.platform.domain.events.user_events import UserForcedLogout
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.quality.domain.events.document_events import DocumentEditingEnded
from src.modules.quality.domain.events.document_events import DocumentEditingTakenOver
from src.modules.quality.domain.events.document_events import DocumentMarkedInvalid
from src.modules.quality.domain.events.document_events import DocumentRevised
from src.modules.workspace.domain.events.product_events import ProductUpdated
from src.modules.workspace.domain.events.project_events import ProjectCreated
from src.modules.workspace.domain.events.project_events import ProjectUpdated
from tests.unit.fakes import FakeUnitOfWork


class FakeNotificationRepository:
    def __init__(self, existing_source_event_ids: set[str] | None = None):
        self.saved = []
        self._existing = existing_source_event_ids or set()

    async def exists_by_source_event_id(self, source_event_id: str) -> bool:
        return source_event_id in self._existing

    async def save(self, notification):
        self.saved.append(notification)
        return notification

    async def add_for_event(self, notification):
        self.saved.append(notification)
        return True


class FakeEmailNotificationRepository:
    def __init__(self):
        self.saved = []

    async def save(self, notification):
        self.saved.append(notification)
        return notification


def make_handler(existing: set[str] | None = None):
    inapp = FakeNotificationRepository(existing)
    emails = FakeEmailNotificationRepository()
    return HandleEventNotifications(inapp, emails, uow=FakeUnitOfWork()), inapp, emails


# ── Event mail fakes ──────────────────────────────────────────────────


def make_user(
    id: int = 4,
    email: str = "user@example.com",
    full_name: str = "Jamie Appleseed",
    language: str = "enGB",
    is_active: bool = True,
) -> SimpleNamespace:
    """A bare stand-in for User: HandleEventNotifications only ever reads
    these four attributes off whatever IUserRepository.get_by_id returns."""
    return SimpleNamespace(
        id=id, email=email, full_name=full_name, language=language, is_active=is_active
    )


class FakeUserRepositoryForEvents:
    def __init__(self, users: dict[int, SimpleNamespace] | None = None) -> None:
        self._users = users or {}

    async def get_by_id(self, id: int) -> SimpleNamespace | None:
        return self._users.get(id)


class FakeAdminSettingsRepoForEvents:
    """Minimal stand-in: HandleEventNotifications only ever reads
    get_features().enable_email_notifications and get_mail().enabled."""

    def __init__(self, enable_email_notifications: bool = True, mail_enabled: bool = True) -> None:
        self._features = SimpleNamespace(enable_email_notifications=enable_email_notifications)
        self._mail = SimpleNamespace(enabled=mail_enabled)

    async def get_features(self) -> SimpleNamespace:
        return self._features

    async def get_mail(self) -> SimpleNamespace:
        return self._mail


class FakeMailServiceForEvents:
    def __init__(self, raise_on_send: Exception | None = None) -> None:
        self.sent: list[dict] = []
        self._raise = raise_on_send

    async def send_system_mail(self, kind, to, language=None, **ctx):
        if self._raise is not None:
            raise self._raise
        self.sent.append({"kind": kind, "to": to, "language": language, **ctx})


def make_handler_with_mail(
    *,
    existing: set[str] | None = None,
    users: dict[int, SimpleNamespace] | None = None,
    enable_email_notifications: bool = True,
    mail_enabled: bool = True,
    mail_raises: Exception | None = None,
):
    inapp = FakeNotificationRepository(existing)
    emails = FakeEmailNotificationRepository()
    user_repo = FakeUserRepositoryForEvents(users)
    settings_repo = FakeAdminSettingsRepoForEvents(enable_email_notifications, mail_enabled)
    mail_service = FakeMailServiceForEvents(mail_raises)
    handler = HandleEventNotifications(
        inapp,
        emails,
        user_repo=user_repo,
        mail_service=mail_service,
        admin_settings_repo=settings_repo,
        uow=FakeUnitOfWork(),
    )
    return handler, inapp, emails, mail_service


def fulfilled_event(**kwargs):
    defaults = dict(
        demand_id=1,
        item_article_name="Resistor 10k",
        old_status=BoughtItemDemandStatus.ORDERED,
        new_status=BoughtItemDemandStatus.FULFILLED,
        actor_id=7,
        notify_on_delivery=True,
        creator_id=4,
        order_id=5,
        order_item_id=9,
    )
    defaults.update(kwargs)
    return DemandItemStatusChanged(**defaults)


# ── Demand status changes ─────────────────────────────────────────────


async def test_fulfilled_demand_creates_inapp_and_email():
    handler, inapp, emails = make_handler()

    await handler.execute(fulfilled_event(), "1-0")

    (notification,) = inapp.saved
    assert notification.user_id == 4
    assert notification.type == NotificationType.DEMAND_ITEM_FULFILLED
    assert "Resistor 10k" in notification.message
    assert notification.demand_item_id == 1
    # make_notification's context links are exclusive: like every sibling
    # branch in the same method, this one sets demand_item_id alone.
    assert notification.order_id is None
    assert notification.source_event_id == "1-0"

    (email,) = emails.saved
    assert email.reason == "delivered"
    assert email.receiver_id == 4
    assert email.demand_item_id == 1
    assert email.order_item_id == 9


async def test_fulfilled_without_notify_flag_is_silent():
    handler, inapp, emails = make_handler()
    await handler.execute(fulfilled_event(notify_on_delivery=False), "1-0")
    assert inapp.saved == []
    assert emails.saved == []


async def test_canceled_demand_notifies_creator():
    handler, inapp, emails = make_handler()

    await handler.execute(
        fulfilled_event(new_status=BoughtItemDemandStatus.CANCELED, actor_id=7, creator_id=4),
        "1-0",
    )

    (notification,) = inapp.saved
    assert notification.type == NotificationType.DEMAND_ITEM_CANCELED
    assert notification.user_id == 4
    assert emails.saved == []


async def test_canceled_by_creator_is_silent():
    handler, inapp, _ = make_handler()
    await handler.execute(
        fulfilled_event(new_status=BoughtItemDemandStatus.CANCELED, actor_id=4, creator_id=4),
        "1-0",
    )
    assert inapp.saved == []


# ── Made-item demand status changes ────────────────────────────────────


def made_item_fulfilled_event(**kwargs):
    defaults = dict(
        demand_id=1,
        item_article_name="Bracket",
        old_status=MadeItemDemandStatus.ALLOCATED,
        new_status=MadeItemDemandStatus.FULFILLED,
        actor_id=7,
        notify_on_delivery=True,
        creator_id=4,
    )
    defaults.update(kwargs)
    return MadeItemDemandItemStatusChanged(**defaults)


async def test_made_item_fulfilled_demand_creates_inapp_and_email():
    handler, inapp, emails = make_handler()

    await handler.execute(made_item_fulfilled_event(), "1-0")

    (notification,) = inapp.saved
    assert notification.user_id == 4
    assert notification.type == NotificationType.DEMAND_ITEM_FULFILLED
    assert "Bracket" in notification.message
    assert notification.demand_item_id == 1
    assert notification.source_event_id == "1-0"

    (email,) = emails.saved
    assert email.reason == "delivered"
    assert email.receiver_id == 4
    assert email.demand_item_id == 1
    assert email.order_item_id is None


async def test_made_item_fulfilled_without_notify_flag_is_silent():
    handler, inapp, emails = make_handler()
    await handler.execute(made_item_fulfilled_event(notify_on_delivery=False), "1-0")
    assert inapp.saved == []
    assert emails.saved == []


async def test_made_item_canceled_demand_notifies_creator():
    handler, inapp, emails = make_handler()

    await handler.execute(
        made_item_fulfilled_event(
            new_status=MadeItemDemandStatus.CANCELED, actor_id=7, creator_id=4
        ),
        "1-0",
    )

    (notification,) = inapp.saved
    assert notification.type == NotificationType.DEMAND_ITEM_CANCELED
    assert notification.user_id == 4
    assert emails.saved == []


async def test_made_item_canceled_by_creator_is_silent():
    handler, inapp, _ = make_handler()
    await handler.execute(
        made_item_fulfilled_event(
            new_status=MadeItemDemandStatus.CANCELED, actor_id=4, creator_id=4
        ),
        "1-0",
    )
    assert inapp.saved == []


# ── Source item demand status changes ──────────────────────────────────


def source_item_fulfilled_event(**kwargs):
    defaults = dict(
        demand_id=3,
        lot_id=8,
        material_name="Aluminium Bar 20x20x1000",
        old_status=SourceItemDemandStatus.ORDERED,
        new_status=SourceItemDemandStatus.FULFILLED,
        actor_id=7,
        notify_on_delivery=True,
        creator_id=4,
    )
    defaults.update(kwargs)
    return SourceItemDemandStatusChanged(**defaults)


async def test_source_item_fulfilled_demand_creates_inapp_and_email():
    handler, inapp, emails = make_handler()

    await handler.execute(source_item_fulfilled_event(), "1-0")

    (notification,) = inapp.saved
    assert notification.user_id == 4
    assert notification.type == NotificationType.DEMAND_ITEM_FULFILLED
    assert "Aluminium Bar 20x20x1000" in notification.message
    assert notification.demand_item_id == 3
    (email,) = emails.saved
    assert (email.reason, email.receiver_id, email.demand_item_id) == ("delivered", 4, 3)


async def test_source_item_fulfilled_without_notify_flag_is_silent():
    handler, inapp, emails = make_handler()
    await handler.execute(source_item_fulfilled_event(notify_on_delivery=False), "1-0")
    assert inapp.saved == []
    assert emails.saved == []


async def test_source_item_canceled_demand_notifies_its_creator_unless_they_canceled_it():
    handler, inapp, emails = make_handler()
    canceled = SourceItemDemandStatus.CANCELED

    await handler.execute(source_item_fulfilled_event(new_status=canceled, actor_id=4), "1-0")
    assert inapp.saved == []

    await handler.execute(source_item_fulfilled_event(new_status=canceled, actor_id=7), "2-0")
    (notification,) = inapp.saved
    assert notification.type == NotificationType.DEMAND_ITEM_CANCELED
    assert notification.user_id == 4
    assert emails.saved == []


# ── Order cancellation ────────────────────────────────────────────────


async def test_order_canceled_notifies_creator():
    handler, inapp, _ = make_handler()

    await handler.execute(
        OrderCanceled(order_id=5, order_number="ORD-1", actor_id=7, supplier_id=2, creator_id=4),
        "1-0",
    )

    (notification,) = inapp.saved
    assert notification.type == NotificationType.ORDER_CANCELED
    assert notification.user_id == 4
    assert notification.order_id == 5


async def test_order_canceled_by_creator_is_silent():
    handler, inapp, _ = make_handler()
    await handler.execute(
        OrderCanceled(order_id=5, order_number="ORD-1", actor_id=4, supplier_id=2, creator_id=4),
        "1-0",
    )
    assert inapp.saved == []


# ── Project / product assignment ──────────────────────────────────────


async def test_project_created_notifies_designated_user():
    handler, inapp, _ = make_handler()

    await handler.execute(
        ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4),
        "1-0",
    )

    (notification,) = inapp.saved
    assert notification.type == NotificationType.PROJECT_ASSIGNED
    assert notification.user_id == 4
    assert notification.project_id == 1


async def test_project_created_for_self_is_silent():
    handler, inapp, _ = make_handler()
    await handler.execute(
        ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=7),
        "1-0",
    )
    assert inapp.saved == []


async def test_project_updated_notifies_only_on_reassignment():
    handler, inapp, _ = make_handler()

    await handler.execute(
        ProjectUpdated(
            project_id=1,
            project_number="P-1",
            actor_id=7,
            designated_user_id=4,
            old_designated_user_id=4,  # unchanged
        ),
        "1-0",
    )
    assert inapp.saved == []

    await handler.execute(
        ProjectUpdated(
            project_id=1,
            project_number="P-1",
            actor_id=7,
            designated_user_id=4,
            old_designated_user_id=2,  # reassigned
        ),
        "1-1",
    )
    (notification,) = inapp.saved
    assert notification.user_id == 4


async def test_product_updated_notifies_new_designated_user():
    handler, inapp, _ = make_handler()

    await handler.execute(
        ProductUpdated(
            product_id=3,
            product_number="PR-1",
            actor_id=7,
            designated_user_id=4,
            old_designated_user_id=2,
        ),
        "1-0",
    )

    (notification,) = inapp.saved
    assert notification.type == NotificationType.PRODUCT_ASSIGNED
    assert notification.product_id == 3


# ── User administration ───────────────────────────────────────────────


async def test_permissions_changed_notifies_target():
    handler, inapp, _ = make_handler()
    await handler.execute(UserPermissionsChanged(user_id=4, actor_id=7), "1-0")
    (notification,) = inapp.saved
    assert notification.type == NotificationType.PERMISSIONS_CHANGED
    assert notification.user_id == 4


async def test_self_permission_change_is_silent():
    handler, inapp, _ = make_handler()
    await handler.execute(UserPermissionsChanged(user_id=7, actor_id=7), "1-0")
    assert inapp.saved == []


async def test_deactivation_notifies_target():
    handler, inapp, _ = make_handler()
    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")
    (notification,) = inapp.saved
    assert notification.type == NotificationType.ACCOUNT_DEACTIVATED


async def test_forced_logout_always_notifies():
    handler, inapp, _ = make_handler()
    await handler.execute(UserForcedLogout(user_id=4, actor_id=7), "1-0")
    (notification,) = inapp.saved
    assert notification.type == NotificationType.FORCED_LOGOUT
    assert notification.user_id == 4


async def test_editing_taken_over_notifies_the_previous_editor():
    handler, inapp, emails = make_handler()
    await handler.execute(
        DocumentEditingTakenOver(
            resource="checklists",
            document_id=12,
            title="Press 12",
            previous_editor_id=4,
            actor_id=7,
            actor_name="Jane Doe",
        ),
        "1-0",
    )
    (notification,) = inapp.saved
    assert notification.type == NotificationType.EDITING_TAKEN_OVER
    assert notification.user_id == 4
    assert "Jane Doe" in notification.message and "'Press 12'" in notification.message
    assert emails.saved == []


async def test_document_marked_invalid_notifies_everyone_involved_but_the_actor():
    handler, inapp, _ = make_handler()
    await handler.execute(
        DocumentMarkedInvalid(
            resource="calculations",
            document_id=5,
            title="Lift axis",
            revision="B",
            reason="Wrong load",
            actor_id=7,
            actor_name="Jane Doe",
            recipient_ids=[4, 7, 9],
        ),
        "2-0",
    )
    assert sorted(n.user_id for n in inapp.saved) == [4, 9]
    assert {n.type for n in inapp.saved} == {NotificationType.DOCUMENT_MARKED_INVALID}
    assert "Wrong load" in inapp.saved[0].message


async def test_document_revised_notifies_everyone_involved_but_the_actor():
    handler, inapp, _ = make_handler()
    await handler.execute(
        DocumentRevised(
            resource="checklists",
            document_id=6,
            title="Press 12",
            revision="C",
            previous_revision="B",
            reason="Pump replaced",
            actor_id=4,
            actor_name="Jane Doe",
            recipient_ids=[4, 9],
        ),
        "3-0",
    )
    (notification,) = inapp.saved
    assert (notification.user_id, notification.type) == (9, NotificationType.DOCUMENT_REVISED)


async def test_document_editing_ended_notifies_the_editor():
    handler, inapp, _ = make_handler()
    await handler.execute(
        DocumentEditingEnded(
            resource="checklists",
            document_id=6,
            title="Press 12",
            previous_editor_id=9,
            actor_id=4,
            actor_name="Jane Doe",
        ),
        "4-0",
    )
    (notification,) = inapp.saved
    assert (notification.user_id, notification.type) == (9, NotificationType.EDITING_ENDED)


# ── Idempotency and pass-through ──────────────────────────────────────


async def test_redelivered_message_is_skipped():
    handler, inapp, emails = make_handler(existing={"1-0"})
    await handler.execute(fulfilled_event(), "1-0")
    assert inapp.saved == []
    assert emails.saved == []


async def test_events_without_notification_rules_are_ignored():
    handler, inapp, emails = make_handler()
    await handler.execute(BoughtItemCreated(item_id=1, article_name="X", creator_id=7), "1-0")
    assert inapp.saved == []
    assert emails.saved == []


# ── Event mail ─────────────────────────────────────────────────────────


async def test_no_mail_wiring_at_all_is_a_silent_no_op():
    """The two-positional-arg construction (make_handler, used by every
    test above) wires no mail: mail sending is skipped entirely, only the
    in-app row still gets created."""
    handler, inapp, _ = make_handler()
    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")
    assert len(inapp.saved) == 1


async def test_account_deactivated_sends_mail_even_though_the_user_is_now_inactive():
    """The target user's own row already reads is_active=False by the
    time this handler runs (this IS the deactivation); unlike every
    other event mail below, this one must send anyway: an in-app
    notification is useless to someone who can no longer log in."""
    user = make_user(id=4, is_active=False)
    handler, _, _, mail = make_handler_with_mail(users={4: user})

    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")

    (sent,) = mail.sent
    assert sent["kind"] == MailTemplateKind.ACCOUNT_DEACTIVATED
    assert sent["to"] == user.email
    assert sent["language"] == user.language
    assert sent["full_name"] == user.full_name


async def test_self_deactivation_never_sends_mail():
    handler, _, _, mail = make_handler_with_mail(users={7: make_user(id=7)})
    await handler.execute(UserDeactivated(user_id=7, actor_id=7), "1-0")
    assert mail.sent == []


async def test_permissions_changed_sends_mail_to_the_active_target():
    user = make_user(id=4)
    handler, _, _, mail = make_handler_with_mail(users={4: user})

    await handler.execute(UserPermissionsChanged(user_id=4, actor_id=7), "1-0")

    (sent,) = mail.sent
    assert sent["kind"] == MailTemplateKind.PERMISSIONS_CHANGED
    assert sent["to"] == user.email


async def test_permissions_changed_skips_mail_for_an_inactive_target():
    """Unlike account_deactivated, there is nothing useful to tell an
    already-inactive account about a permission change."""
    user = make_user(id=4, is_active=False)
    handler, _, _, mail = make_handler_with_mail(users={4: user})

    await handler.execute(UserPermissionsChanged(user_id=4, actor_id=7), "1-0")

    assert mail.sent == []


async def test_self_permission_change_never_sends_mail():
    handler, _, _, mail = make_handler_with_mail(users={7: make_user(id=7)})
    await handler.execute(UserPermissionsChanged(user_id=7, actor_id=7), "1-0")
    assert mail.sent == []


async def test_project_assigned_sends_mail_with_the_project_number():
    user = make_user(id=4)
    handler, _, _, mail = make_handler_with_mail(users={4: user})

    await handler.execute(
        ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4),
        "1-0",
    )

    (sent,) = mail.sent
    assert sent["kind"] == MailTemplateKind.PROJECT_ASSIGNED
    assert sent["project_number"] == "P-1"
    assert sent["full_name"] == user.full_name


async def test_project_reassignment_notifies_only_the_new_designated_user_by_mail():
    handler, _, _, mail = make_handler_with_mail(users={4: make_user(id=4), 2: make_user(id=2)})

    await handler.execute(
        ProjectUpdated(
            project_id=1,
            project_number="P-1",
            actor_id=7,
            designated_user_id=4,
            old_designated_user_id=4,  # unchanged
        ),
        "1-0",
    )
    assert mail.sent == []

    await handler.execute(
        ProjectUpdated(
            project_id=1,
            project_number="P-1",
            actor_id=7,
            designated_user_id=4,
            old_designated_user_id=2,  # reassigned
        ),
        "1-1",
    )
    (sent,) = mail.sent
    assert sent["to"] == "user@example.com"


async def test_product_assigned_sends_mail_with_the_product_number():
    user = make_user(id=4)
    handler, _, _, mail = make_handler_with_mail(users={4: user})

    await handler.execute(
        ProductUpdated(
            product_id=3,
            product_number="PR-1",
            actor_id=7,
            designated_user_id=4,
            old_designated_user_id=2,
        ),
        "1-0",
    )

    (sent,) = mail.sent
    assert sent["kind"] == MailTemplateKind.PRODUCT_ASSIGNED
    assert sent["product_number"] == "PR-1"


async def test_no_mail_when_the_email_notifications_feature_is_off():
    user = make_user(id=4)
    handler, _, _, mail = make_handler_with_mail(users={4: user}, enable_email_notifications=False)
    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")
    assert mail.sent == []


async def test_no_mail_when_mail_is_disabled():
    user = make_user(id=4)
    handler, _, _, mail = make_handler_with_mail(users={4: user}, mail_enabled=False)
    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")
    assert mail.sent == []


async def test_missing_user_lookup_is_a_silent_no_op():
    handler, _, _, mail = make_handler_with_mail(users={})
    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")
    assert mail.sent == []


async def test_a_mail_failure_is_swallowed_the_inapp_row_still_stands():
    user = make_user(id=4)
    handler, inapp, _, mail = make_handler_with_mail(
        users={4: user}, mail_raises=RuntimeError("smtp exploded")
    )

    await handler.execute(UserDeactivated(user_id=4, actor_id=7), "1-0")

    (notification,) = inapp.saved
    assert notification.type == NotificationType.ACCOUNT_DEACTIVATED
    assert mail.sent == []
