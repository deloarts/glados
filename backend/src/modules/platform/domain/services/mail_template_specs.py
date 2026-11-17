"""
One declaration per MailTemplateKind, read by InitDatabase's seeder, the
resolution service, the admin settings API and (via the API) the editor
dialog's variable chips. Adding a kind means adding one entry here plus
optional shipped `<kind>.<language>.html` files, never a frontend change.

`family` is what the editor branches its preview mode on, never
`kind == MailTemplateKind.WELCOME`, which would not scale past the first
kind:

  - SYSTEM   - rendered here, in the backend, as a full HTML document
               (welcome, the notification digest, schedule/disk alerts, ...).
               Previewed by rendering the *draft* through the real Jinja
               string env (render.render_string) with `sample_context`, so
               the preview is byte-identical to what actually gets sent.
  - SUPPLIER: resolved in the frontend order composer against `{{ table }}`
               tokens and a handful of plain vars; a supplier's own template
               still wins over the admin default. Previewed entirely in the
               frontend, never through the backend string env; it is
               `{{ var }}` substitution, not real Jinja, and a `{% for %}`
               loop in a SYSTEM template would render as literal text there.
"""

from dataclasses import dataclass
from enum import Enum
from enum import unique
from typing import Any

from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind

# Sample domain used by every SYSTEM kind's preview and by the packaged-file
# seed-time subject regex has no opinion on this; it is only ever consumed
# by PreviewMailTemplate, never persisted.
_SAMPLE_DOMAIN = "https://glados.example.com"

_SAMPLE_NOTIFICATION_ITEMS: list[dict[str, Any]] = [
    {"reason": "delivered", "demand_item_id": None, "order_item_id": 4321},
    {
        "reason": "meeting",
        "demand_item_id": None,
        "order_item_id": None,
        "meeting_id": 21,
        "message": "Alex mentioned you twice and assigned you 2 todos in MTG-26-0021.",
    },
]

# The order composer's SIMPLE_VARS (SupplierOrderTemplateDialog.vue), shared
# by both supplier-family kinds: `request` and `order` render the exact
# same variable set, only the recipient and framing differ.
_ORDER_VARIABLES: tuple[str, ...] = (
    "order_number",
    "supplier",
    "note",
    "ordered_date",
    "expected_delivery",
    "total",
    "total_price",
    "user_full_name",
    "user_email",
)

_ORDER_SAMPLE_CONTEXT: dict[str, Any] = {
    "order_number": "ORD-2026-0001",
    "supplier": "Sample Supplier Ltd",
    "note": "Please deliver to the main entrance.",
    "ordered_date": "2026-01-15",
    "expected_delivery": "2026-02-01",
    "total": "4",
    "total_price": "€ 446.00",
    "user_full_name": "Jane Smith",
    "user_email": "jane.smith@example.com",
}


# The variables of the meeting notes mail, filled in by the compose dialog.
_MEETING_NOTES_VARIABLES: tuple[str, ...] = (
    "meeting_name",
    "meeting_number",
    "meeting_date",
    "owner_number",
    "issue",
    "user_full_name",
    "user_email",
)


@unique
class MailTemplateFamily(str, Enum):
    SYSTEM = "system"
    SUPPLIER = "supplier"


@dataclass(frozen=True)
class MailTemplateSpec:
    kind: MailTemplateKind
    family: MailTemplateFamily
    variables: tuple[str, ...]  # drives the editor's variable chips
    default_subject: str  # used only when no row/<title> is configured
    sample_context: dict[str, Any]  # drives the server-side (SYSTEM) preview


MAIL_TEMPLATE_SPECS: dict[MailTemplateKind, MailTemplateSpec] = {
    # ── Kinds sent from a direct send site ───────────────────────────
    MailTemplateKind.WELCOME: MailTemplateSpec(
        kind=MailTemplateKind.WELCOME,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "username", "created_by_name", "created_by_email", "domain"),
        default_subject="Welcome to Glados",
        sample_context={
            "full_name": "Jamie Appleseed",
            "username": "jamie.appleseed",
            "created_by_name": "Alex Admin",
            "created_by_email": "alex.admin@example.com",
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.NOTIFICATION_DIGEST: MailTemplateSpec(
        kind=MailTemplateKind.NOTIFICATION_DIGEST,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "items", "domain"),
        default_subject="Glados – New notifications",
        sample_context={
            "full_name": "Jamie Appleseed",
            "items": _SAMPLE_NOTIFICATION_ITEMS,
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.TEST_MAIL: MailTemplateSpec(
        kind=MailTemplateKind.TEST_MAIL,
        family=MailTemplateFamily.SYSTEM,
        variables=("domain",),
        default_subject="Glados – Test Mail",
        sample_context={"domain": _SAMPLE_DOMAIN},
    ),
    MailTemplateKind.REQUEST: MailTemplateSpec(
        kind=MailTemplateKind.REQUEST,
        family=MailTemplateFamily.SUPPLIER,
        variables=_ORDER_VARIABLES,
        default_subject="Request for quote",
        sample_context=dict(_ORDER_SAMPLE_CONTEXT),
    ),
    MailTemplateKind.ORDER: MailTemplateSpec(
        kind=MailTemplateKind.ORDER,
        family=MailTemplateFamily.SUPPLIER,
        variables=_ORDER_VARIABLES,
        default_subject="Purchase order",
        sample_context=dict(_ORDER_SAMPLE_CONTEXT),
    ),
    # The default text of the meeting notes mail, which the compose dialog
    # fills with plain `{{ var }}` substitution, like the supplier kinds. It
    # ships packaged files that are body fragments, not documents, and is
    # previewed through the server's string env with its sample context,
    # which renders plain variables exactly as the compose dialog does.
    MailTemplateKind.MEETING_NOTES: MailTemplateSpec(
        kind=MailTemplateKind.MEETING_NOTES,
        family=MailTemplateFamily.SYSTEM,
        variables=_MEETING_NOTES_VARIABLES,
        default_subject="Meeting minutes",
        sample_context={
            "meeting_name": "Design Review Gripper",
            "meeting_number": "MTG-26-0021",
            "meeting_date": "6 Nov 2026",
            "owner_number": "26-0142",
            "issue": "2",
            "user_full_name": "Jane Smith",
            "user_email": "jane.smith@example.com",
        },
    ),
    # ── Event-driven kinds, wired to HandleEventNotifications
    # (account_deactivated/permissions_changed/project_assigned/
    # product_assigned) or SmtpMailService's ops-alert fan-out
    # (schedule_error/disk_space_warning) ─────────────────────────────
    #
    # `variables` here is deliberately narrow: UserDeactivated/
    # UserPermissionsChanged (domain/events/user_events.py) carry only
    # user_id/actor_id, and ProjectCreated/Updated /
    # ProductCreated/Updated (domain/events/{project,product}_events.py)
    # carry only their *_number, never a name/description field, so
    # `full_name` comes from the looked-up User entity (see
    # HandleEventNotifications._send_to_user) and the assignment kinds
    # get the bare `*_number`, not an invented `*_name`.
    MailTemplateKind.ACCOUNT_DEACTIVATED: MailTemplateSpec(
        kind=MailTemplateKind.ACCOUNT_DEACTIVATED,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "domain"),
        default_subject="Your Glados account has been deactivated",
        sample_context={
            "full_name": "Jamie Appleseed",
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.PERMISSIONS_CHANGED: MailTemplateSpec(
        kind=MailTemplateKind.PERMISSIONS_CHANGED,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "domain"),
        default_subject="Your Glados permissions have changed",
        sample_context={
            "full_name": "Jamie Appleseed",
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.PROJECT_ASSIGNED: MailTemplateSpec(
        kind=MailTemplateKind.PROJECT_ASSIGNED,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "project_number", "domain"),
        default_subject="You have been assigned to a project",
        sample_context={
            "full_name": "Jamie Appleseed",
            "project_number": "P-2026-0001",
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.PRODUCT_ASSIGNED: MailTemplateSpec(
        kind=MailTemplateKind.PRODUCT_ASSIGNED,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "product_number", "domain"),
        default_subject="You have been assigned to a product",
        sample_context={
            "full_name": "Jamie Appleseed",
            "product_number": "PR-2026-0001",
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    # SUPPLIER family, same variable set as request/order (the frontend's
    # "notify supplier" action on cancel reuses the order composer);
    # ships no files by design: a supplier-family kind seeds empty until
    # an admin writes one, same as request/order do today.
    MailTemplateKind.ORDER_CANCELED: MailTemplateSpec(
        kind=MailTemplateKind.ORDER_CANCELED,
        family=MailTemplateFamily.SUPPLIER,
        variables=_ORDER_VARIABLES,
        default_subject="Order canceled",
        sample_context=dict(_ORDER_SAMPLE_CONTEXT),
    ),
    MailTemplateKind.SUPPLIER_LINES_TO_SETTLE: MailTemplateSpec(
        kind=MailTemplateKind.SUPPLIER_LINES_TO_SETTLE,
        family=MailTemplateFamily.SYSTEM,
        variables=("full_name", "lot_number", "ended", "open_lines", "canceled_lines", "domain"),
        default_subject="Supplier lines to settle",
        sample_context={
            "full_name": "Jamie Appleseed",
            "lot_number": "LOT-2026-0001",
            "ended": "canceled",
            "open_lines": ["B-2026-0003 pos. 2"],
            "canceled_lines": ["B-2026-0004 pos. 1"],
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.SCHEDULE_ERROR: MailTemplateSpec(
        kind=MailTemplateKind.SCHEDULE_ERROR,
        family=MailTemplateFamily.SYSTEM,
        variables=("task_name", "message", "domain"),
        default_subject="Glados – Schedule error",
        sample_context={
            "task_name": "Nightly Auto-Plan",
            "message": "Sample error detail.",
            "domain": _SAMPLE_DOMAIN,
        },
    ),
    MailTemplateKind.DISK_SPACE_WARNING: MailTemplateSpec(
        kind=MailTemplateKind.DISK_SPACE_WARNING,
        family=MailTemplateFamily.SYSTEM,
        variables=("used_gb", "total_gb", "domain"),
        default_subject="Glados – Disk space warning",
        sample_context={
            "used_gb": 42.5,
            "total_gb": 50.0,
            "domain": _SAMPLE_DOMAIN,
        },
    ),
}
