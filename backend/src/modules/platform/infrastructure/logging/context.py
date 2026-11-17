"""
Per-request context vars propagated automatically into every log record
via ContextFilter. Set them from middleware; read them via logging.
"""

from contextvars import ContextVar
from uuid import UUID

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
username_var: ContextVar[str | None] = ContextVar("username", default=None)
api_key_id_var: ContextVar[int | None] = ContextVar("api_key_id", default=None)
pat_id_var: ContextVar[int | None] = ContextVar("pat_id", default=None)
# The current request's session row public_id (the JWT's `sid` claim).
# Read by "which session is this?" logic, sessions list current-flag,
# password change sparing the session that made it, not just logging.
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
# The client address and user agent of the current request, for the
# security log entries the request writes. Unset outside a request.
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)
user_agent_var: ContextVar[str | None] = ContextVar("user_agent", default=None)


def current_session_id() -> UUID | None:
    """The public id of the session that made the current request, or None
    when the request carries no session or the stored value is not a UUID."""
    sid = session_id_var.get()
    if not sid:
        return None
    try:
        return UUID(sid)
    except ValueError:
        return None
