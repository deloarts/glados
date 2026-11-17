"""Permission rules for API keys and PATs. Both are long-lived bearer
credentials, so they never carry settings access or the ability to mint
API keys, and never exceed their creator's permissions. The terminal
connect permission is never grantable either: only CreateTerminalKey sets
it, on a key that holds nothing else.

Also defines the scopes the SolidWorks add-ins need, so the web UI's token
shortcuts never hardcode them.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.value_objects.permission import Permission

NEVER_GRANTABLE_TO_TOKENS: frozenset[str] = frozenset(
    {
        Permission.READ_SETTINGS,
        Permission.WRITE_SETTINGS,
        Permission.MANAGE_API_KEYS,
        Permission.CONNECT_TERMINALS,
    }
)

# The only permission of a terminal key. A key holding it is refused on the
# key router (auth_deps.get_current_api_key_user) and accepted only when an
# unknown device starts its first terminal session.
TERMINAL_KEY_SCOPES: tuple[str, ...] = (Permission.CONNECT_TERMINALS,)

# The SolidWorks add-in's PAT. It has two gated calls: creating source items
# needs write:source_items, and the EPLAN Data Portal match, search and
# picture need use:data_portal. Every other pat endpoint it uses only needs
# a valid token, the Data Portal status included.
SOLIDWORKS_ADDIN_SCOPES: tuple[str, ...] = (
    Permission.WRITE_SOURCE_ITEMS,
    Permission.USE_DATA_PORTAL,
)

# The vault add-in's PAT, one per Windows user. Its file-changed call and its
# file history view both need the add-in permission, deliberately nothing
# item-shaped.
PDM_ADDIN_SCOPES: tuple[str, ...] = (Permission.USE_PDM_ADDIN,)

# An AI agent's token. The read preset only opens the MCP surface; the draft
# preset adds the permissions of the draft tools (a purchase order, a quote
# request, a production lot, meeting notes), which a user can only grant
# when they hold them.
AGENT_READ_SCOPES: tuple[str, ...] = (Permission.USE_MCP,)
AGENT_DRAFT_SCOPES: tuple[str, ...] = (
    Permission.USE_MCP,
    Permission.WRITE_ORDERS,
    Permission.WRITE_LOTS,
    Permission.WRITE_MEETINGS,
)


def assert_requested_permissions_allowed(
    requested: list[str],
    actor: User,
    *,
    exception_class: type[DomainError],
    noun: str,
) -> None:
    """Raises `exception_class` on the first unknown, never-grantable or
    not-held permission in a new token's request."""
    unknown = set(requested) - set(Permission.ALL)
    if unknown:
        raise exception_class(f"Unknown permission(s): {sorted(unknown)}.")

    disallowed = set(requested) & NEVER_GRANTABLE_TO_TOKENS
    if disallowed:
        raise exception_class(f"{noun} can never be granted: {sorted(disallowed)}.")

    if not actor.is_systemuser:
        not_held = set(requested) - set(actor.effective_permissions)
        if not_held:
            raise exception_class(f"Cannot grant permissions you do not hold: {sorted(not_held)}.")
