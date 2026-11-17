"""
Shapes for the live row-sync signal: a thin, row-identity-only hint telling
connected clients "this row changed, go refetch it", never row data. See
src/modules/platform/adapters/outbound/persistence/change_tracking.py for how these are
produced and src/modules/platform/adapters/inbound/api/live/hub.py for how they're delivered.
"""

from dataclasses import dataclass
from typing import Literal

LiveAction = Literal["created", "updated", "deleted", "bulk"]


class LiveResource:
    """Canonical API path segment for each resource's list endpoint.

    Doubles as the vocabulary for two consumers: live-sync topics (a subset,
    see change_tracking.MODEL_TOPICS) that clients subscribe to and refetch
    through when a row changes, and public_id resolution
    (public_id_lookup._REGISTRY) so a resolved public_id tells the frontend
    which route to send a scan to. Both need the same path-segment value,
    so it's defined once here rather than duplicated."""

    ORDERS = "orders"
    BOUGHT_ITEM_DEMANDS = "bought-items-demands"
    MADE_ITEM_DEMANDS = "made-items-demands"
    SOURCE_ITEM_DEMANDS = "source-item-demands"
    PRODUCTION_LOTS = "production-lots"
    PRODUCTION_ORDERS = "production-orders"
    PRODUCTION_MACHINES = "production-machines"
    MACHINE_POOLS = "production-machine-pools"
    PRODUCTS = "products"
    CUSTOMERS = "customers"
    PROJECTS = "projects"
    SUPPLIERS = "suppliers"
    ARTICLE_GROUPS = "article-groups"
    FABRICATION_METHODS = "fabrication-methods"
    SOURCE_ITEM_TYPES = "source-item-types"
    SOURCE_ITEMS = "source-items"
    BOUGHT_ITEMS = "bought-items"
    MADE_ITEMS = "made-items"
    USERS = "users"
    PRINTERS = "printers"
    CALCULATIONS = "calculations"
    CHECKLISTS = "checklists"
    SEQUENCES = "sequences"
    QUOTE_REQUESTS = "quote-requests"
    # A meeting and everything on its page: attendees, cards, decisions,
    # todos and files signal the meeting's id, so the meeting page and the
    # meeting lists refetch.
    MEETINGS = "meetings"
    # Live-sync topics but not public_id-resolvable. Contacts are personal
    # data, so only readers of contacts receive them (see
    # adapters/inbound/api/live/hub.py). The two link topics carry the id of
    # the product or project whose contact links changed.
    CONTACTS = "contacts"
    PRODUCT_CONTACTS = "product-contacts"
    PROJECT_CONTACTS = "project-contacts"
    # Signalled with the product id whenever one of the product's devices or
    # their components changes, so a product's Devices tab refetches its
    # list. Not public_id-resolvable.
    PRODUCT_DEVICES = "product-devices"
    # A live-sync topic but not public_id-resolvable. Any change to the banner
    # settings, an acknowledgement or a recipient signals it (see
    # change_tracking.MODEL_TOPICS); clients refetch /announcements/me and the
    # admin panel refetches its acknowledgement and recipient lists.
    ANNOUNCEMENTS = "announcements"
    # Live-sync topics but not public_id-resolvable. The terminals and
    # infoscreens tabs follow their rows through these, and a terminal's own
    # live stream receives its own row and its screen's row (see
    # adapters/inbound/api/live/hub.py).
    TERMINALS = "terminals"
    INFOSCREENS = "infoscreens"
    # The default display schedule. The infoscreens page refetches it, and
    # every approved display showing a screen reads its state again.
    INFOSCREEN_DEFAULTS = "infoscreen-defaults"
    # A live-sync topic but not public_id-resolvable. Sending or ending a
    # message to terminals signals it; the terminals page refetches its
    # active messages and every approved display reads its state again.
    TERMINAL_BROADCASTS = "terminal-broadcasts"

    # Not backed by a table, so it is neither a live-sync topic nor
    # public_id-resolvable. Someone edits a meeting card: the id is the
    # card's, the actor the editing user, "updated" a heartbeat while they
    # edit and "deleted" when they stop. A viewer shows the editor until 45
    # seconds after the last heartbeat.
    MEETING_CARD_PRESENCE = "meeting-card-presence"

    # Not backed by a table, so it is neither a live-sync topic nor
    # public_id-resolvable. It is published only as a refetch hint (id=0,
    # action="updated") when an Auto-Plan run starts and ends.
    AUTO_PLAN_RUN = "auto-plan-run"


@dataclass(frozen=True)
class LiveSignal:
    resource: str
    id: int  # meaningless (0) when action == "bulk", clients refetch the page instead
    action: LiveAction
    actor_id: int | None
