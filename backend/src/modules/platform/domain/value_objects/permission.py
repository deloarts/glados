"""Canonical permission strings. Using these instead of literals turns
typos into import-time errors."""

from typing import ClassVar


class Permission:
    # Bought items (catalogue)
    WRITE_BOUGHT_ITEMS = "write:bought_items"
    DELETE_BOUGHT_ITEMS = "delete:bought_items"

    # Made items (catalogue)
    WRITE_MADE_ITEMS = "write:made_items"
    DELETE_MADE_ITEMS = "delete:made_items"

    # Source items (catalogue)
    WRITE_SOURCE_ITEMS = "write:source_items"
    DELETE_SOURCE_ITEMS = "delete:source_items"

    # Source item types. As with every small reference list below, write
    # covers archiving and restoring entries too, since both can be undone.
    WRITE_SOURCE_ITEM_TYPES = "write:source_item_types"

    # Demand items
    WRITE_DEMAND_ITEMS = "write:demand_items"
    MANAGE_DEMAND_ITEMS = "manage:demand_items"  # update others' or terminal-status items

    # Orders
    WRITE_ORDERS = "write:orders"
    MANAGE_ORDERS = "manage:orders"  # update non-draft orders
    # Receiving goods is a warehouse action and must not imply editing orders.
    RECEIVE_DELIVERIES = "receive:deliveries"

    # Allocations
    WRITE_ALLOCATIONS = "write:allocations"

    # Suppliers
    WRITE_SUPPLIERS = "write:suppliers"
    DELETE_SUPPLIERS = "delete:suppliers"

    # Contacts: the people of customers and suppliers and their links to
    # products and projects. They are personal data, so reading them needs a
    # permission of its own, unlike most master data. Write covers creating,
    # editing, archiving and restoring contacts, and anonymising them together
    # with manage:meetings. Linking them to a product or project follows that
    # record's own edit rights.
    READ_CONTACTS = "read:contacts"
    WRITE_CONTACTS = "write:contacts"

    # Meetings of projects and products (see Meeting). Every signed-in user
    # reads every meeting, so there is no read permission. Write covers
    # creating and editing meetings, their cards, decisions, todos and
    # files. Manage covers marking a meeting invalid, restoring it,
    # deleting it and anonymising its attendees; anonymising a contact needs
    # it together with write:contacts, since that reaches the meetings too.
    WRITE_MEETINGS = "write:meetings"
    MANAGE_MEETINGS = "manage:meetings"

    # Article groups and product families
    WRITE_ARTICLE_GROUPS = "write:article_groups"

    # Fabrication methods
    WRITE_FABRICATION_METHODS = "write:fabrication_methods"

    # Inspection methods: the catalogue of QA checkpoints (visual inspection,
    # measurement, ...) a lot/made-item step can reference, separate from
    # WRITE_INSPECTIONS below (that one gates recording an inspection
    # completion, this one gates editing the catalogue itself).
    WRITE_INSPECTION_METHODS = "write:inspection_methods"

    # Production lots
    WRITE_LOTS = "write:lots"
    MANAGE_LOTS = "manage:lots"  # edit committed (non-DRAFT) lots, cancel
    # QA/inspection: recording an inspection completion (accepted/rejected +
    # disposition) and its evidence files. Separate from WRITE_LOTS/
    # WRITE_PRODUCTION_ORDERS on purpose: a shop-floor QA inspector signs
    # off on a checkpoint, which is a different responsibility from routing
    # edits or fabrication order completion.
    WRITE_INSPECTIONS = "write:inspections"

    # Production machines, machine pools and the tenant holidays
    WRITE_MACHINES = "write:machines"

    # Production orders
    WRITE_PRODUCTION_ORDERS = "write:production_orders"
    # Manage covers pinning and unpinning, cancelling others' orders, the
    # priority override, and reversing a recorded completion, a correction
    # of the shop-floor record kept apart from recording one.
    MANAGE_PRODUCTION_ORDERS = "manage:production_orders"

    # The hand-maintained lists product devices pick from (driving media,
    # kinds with their positions and parameters, component roles, energy
    # behaviours). The devices themselves follow the product's own rule.
    WRITE_PRODUCT_DEVICE_RESOURCES = "write:product_device_resources"

    # Projects
    WRITE_PROJECTS = "write:projects"
    MANAGE_PROJECTS = "manage:projects"  # update/delete any project, assign to other users

    # Saved calculations of the engineering tools (see Calculation). Write
    # covers creating calculations and editing or deleting one's own drafts.
    # Release is its own permission because it is a sign-off, not an edit;
    # the author may release their own work. Manage covers other users'
    # calculations, taking over or ending their editing, and marking a
    # released revision invalid.
    WRITE_CALCULATIONS = "write:calculations"
    RELEASE_CALCULATIONS = "release:calculations"
    MANAGE_CALCULATIONS = "manage:calculations"

    # Inspection checklists (see Checklist). Write covers creating
    # checklists, new revisions, and editing or deleting one's own drafts.
    # Release is the second person's sign-off on a finished checklist and is
    # never given by the creator of that revision. Manage covers other users'
    # checklists, taking over or ending their editing, and marking a
    # released revision invalid.
    WRITE_CHECKLISTS = "write:checklists"
    RELEASE_CHECKLISTS = "release:checklists"
    MANAGE_CHECKLISTS = "manage:checklists"

    # Flow sequences of a product (see Sequence). Write covers creating
    # sequences, new revisions, and editing or deleting one's own drafts.
    # Release is the sign-off and may be given by the author. Manage covers
    # other users' sequences, taking over or ending their editing, and
    # marking a released revision invalid.
    WRITE_SEQUENCES = "write:sequences"
    RELEASE_SEQUENCES = "release:sequences"
    MANAGE_SEQUENCES = "manage:sequences"

    # Personal access tokens (PAT): a user's own self-service bearer tokens,
    # authenticating as that same user (see PersonalAccessToken). A user may
    # hold several at once; each is independently scoped to a permission
    # subset chosen at creation time, capped at the creator's own permissions
    # and never including settings access (see PatRules). Managed by the
    # user themselves at /users/me/personal-access-tokens.
    WRITE_PAT = "write:pat"

    # API keys: admin-issued credentials for a separate, non-interactive
    # service-account identity (see User.is_service_account) with its own
    # scoped-down permission set, capped at the creator's own permissions
    # and never including settings access. NOT the same thing as a PAT
    # above, a PAT impersonates its owning human (just scoped down); an
    # API key is a distinct actor an admin explicitly grants permissions to.
    MANAGE_API_KEYS = "manage:api_keys"

    # AI agents: the gate of the MCP surface (/mcp). Reading in Glados is open
    # to every active user, so a token without this permission, such as the
    # SolidWorks add-in's PAT, must not reach every reader at once through an
    # agent. A PAT or API key carries it only when its owner holds it, so an
    # admin decides who may connect an agent at all. Writes through the agent
    # still need their own permission, such as write:orders for a draft order.
    USE_MCP = "use:mcp"

    # Settings
    READ_SETTINGS = "read:settings"
    WRITE_SETTINGS = "write:settings"

    # Mail: user-composed custom email sent via the instance's own SMTP
    # account (see SendMail), distinct from the system-generated welcome/
    # notification/digest mails, which need no permission because they are
    # never user-authored. Rate-limited on top of this gate; see
    # mail_policy.py.
    SEND_MAIL = "send:mail"

    # Printers and print templates: write covers creating, editing, archiving
    # and restoring printers and editing and resetting the templates.
    WRITE_PRINTERS = "write:printers"
    # The act of printing, separate from editing templates on purpose: a
    # shop-floor operator prints labels/dockets constantly but should not
    # need write:printers (and its ability to edit template source / rebind
    # triggers) just to do so.
    PRINT_DOCUMENTS = "print:documents"

    # The SolidWorks PDM add-in: sending change notifications (POST
    # /api/v1/pat/pdm/files/changed/batch and the API-key routes under
    # {API_KEY}/pdm/files/changed, see RequestPdmFileRefresh) and reading the
    # sync history of named files (POST /api/v1/pat/pdm/files/history, see
    # ListPdmFileHistory). It is the whole add-in token preset each vault user
    # signs in with, so that token can do nothing but enqueue a refresh and
    # read the sync log rows of the files it names, never the items they
    # produced, write:settings or anything item-shaped.
    USE_PDM_ADDIN = "use:pdm_addin"

    # The EPLAN Data Portal lookups: the search behind the create dialog,
    # the exact match on a number the SolidWorks add-in sends, and a part's
    # picture, on the web and the pat surface alike. They only read, but
    # each one spends the organisation's portal token, so an administrator
    # decides who may run them. Creating the bought item afterwards still
    # needs write:bought_items, and the lookup on an existing item with its
    # apply action follows the item's own update right.
    USE_DATA_PORTAL = "use:data_portal"

    # Terminals and infoscreens (see Terminal and Infoscreen). Connect is
    # held only by the service account of a terminal key, which lets an
    # unknown device register itself as a pending terminal and nothing
    # else; it can never be granted to a person's token or a normal API key
    # (token_permission_rules.NEVER_GRANTABLE_TO_TOKENS). Manage covers
    # approving, assigning, revoking, reloading, identifying and deleting
    # terminals. Write covers creating, editing, archiving and restoring
    # screens. Reading both lists and the preview needs no permission.
    CONNECT_TERMINALS = "connect:terminals"
    MANAGE_TERMINALS = "manage:terminals"
    WRITE_INFOSCREENS = "write:infoscreens"

    ALL: ClassVar[list[str]] = [
        WRITE_BOUGHT_ITEMS,
        DELETE_BOUGHT_ITEMS,
        WRITE_MADE_ITEMS,
        DELETE_MADE_ITEMS,
        WRITE_SOURCE_ITEMS,
        DELETE_SOURCE_ITEMS,
        WRITE_SOURCE_ITEM_TYPES,
        WRITE_DEMAND_ITEMS,
        MANAGE_DEMAND_ITEMS,
        WRITE_ORDERS,
        MANAGE_ORDERS,
        RECEIVE_DELIVERIES,
        WRITE_ALLOCATIONS,
        WRITE_SUPPLIERS,
        DELETE_SUPPLIERS,
        READ_CONTACTS,
        WRITE_CONTACTS,
        WRITE_MEETINGS,
        MANAGE_MEETINGS,
        WRITE_ARTICLE_GROUPS,
        WRITE_FABRICATION_METHODS,
        WRITE_INSPECTION_METHODS,
        WRITE_PRODUCT_DEVICE_RESOURCES,
        WRITE_LOTS,
        MANAGE_LOTS,
        WRITE_INSPECTIONS,
        WRITE_MACHINES,
        WRITE_PRODUCTION_ORDERS,
        MANAGE_PRODUCTION_ORDERS,
        WRITE_PROJECTS,
        MANAGE_PROJECTS,
        WRITE_CALCULATIONS,
        RELEASE_CALCULATIONS,
        MANAGE_CALCULATIONS,
        WRITE_CHECKLISTS,
        RELEASE_CHECKLISTS,
        MANAGE_CHECKLISTS,
        WRITE_SEQUENCES,
        RELEASE_SEQUENCES,
        MANAGE_SEQUENCES,
        WRITE_PAT,
        MANAGE_API_KEYS,
        USE_MCP,
        READ_SETTINGS,
        WRITE_SETTINGS,
        SEND_MAIL,
        WRITE_PRINTERS,
        PRINT_DOCUMENTS,
        USE_PDM_ADDIN,
        USE_DATA_PORTAL,
        CONNECT_TERMINALS,
        MANAGE_TERMINALS,
        WRITE_INFOSCREENS,
    ]
