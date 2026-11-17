"""
Whether a request is allowed through while maintenance mode is on.

The admin Maintenance tab (enabled / message / allowed_ips) has existed for
a while as inert plumbing, no backend gate consumed it, so switching it on
had no effect. This module is the single source of truth for who still
gets in: the `system` user unconditionally, whoever can reach the switch
(write:settings) so they can turn it back off, and any client IP the admin
explicitly allowlisted.
"""

import ipaddress

from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.value_objects.permission import Permission

DEFAULT_MESSAGE = "The system is under maintenance. Please try again later."


def normalise_allowed_ips(entries: list[str]) -> list[str]:
    """Strip whitespace, drop empties, de-duplicate (order kept), and
    validate every remaining entry as an IP address or CIDR network.

    Raises ValueError naming the first bad entry, surfaced as a 422 by the
    Pydantic field_validator that calls this, not a domain exception: it's
    a request-shape problem, not something a caller can recover from at
    runtime.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in entries:
        entry = raw.strip()
        if not entry:
            continue
        if entry in seen:
            continue
        try:
            ipaddress.ip_address(entry)
        except ValueError:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                raise ValueError(f"{raw!r} is not a valid IP address or CIDR network.") from None
        seen.add(entry)
        result.append(entry)
    return result


def ip_is_allowed(client_ip: str | None, allowed_ips: list[str]) -> bool:
    """Whether `client_ip` matches one of the stored `allowed_ips` entries,
    exactly or by falling inside a CIDR network.

    False for a missing client address (nothing to compare against) or one
    that fails to parse. A stored entry that fails to parse is skipped
    rather than raised, normalise_allowed_ips already rejects bad entries
    on the way in, but this must never blow up a live request over a row
    edited directly in the DB.
    """
    if not client_ip:
        return False
    try:
        client = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in allowed_ips:
        try:
            if client == ipaddress.ip_address(entry):
                return True
        except ValueError:
            try:
                if client in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
    return False


def is_exempt(user: User, settings: AdminMaintenanceSettings, client_ip: str | None) -> bool:
    """Whether `user` bypasses the maintenance block entirely.

    There are three independent ways in, and any one is sufficient. The
    system user bypasses unconditionally, the same break-glass reasoning as
    login_policy.assert_local_login_allowed: it must always be the way back
    in, regardless of what else is misconfigured. Holding write:settings,
    the permission that can reach the Maintenance tab and turn the switch
    back off, is also sufficient; `User.has_permission` already returns
    True for is_systemuser, so this branch alone would cover it too, but
    the system user is checked first and explicitly so the exemption holds
    even if that permission model ever changes. Finally, an allowlisted
    client IP exempts the admin who wants to keep working from a known
    machine without holding write:settings personally.
    """
    if user.is_systemuser:
        return True
    if user.has_permission(Permission.WRITE_SETTINGS):
        return True
    return ip_is_allowed(client_ip, settings.allowed_ips)


def assert_maintenance_allows(
    user: User, settings: AdminMaintenanceSettings, client_ip: str | None
) -> None:
    """No-op when maintenance mode is off or `user` is exempt; otherwise
    raises MaintenanceModeError with the admin's message, or the fixed
    fallback when none was set."""
    if not settings.enabled:
        return
    if is_exempt(user, settings, client_ip):
        return
    raise MaintenanceModeError(settings.message or DEFAULT_MESSAGE)
