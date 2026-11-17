"""
Which hosts a printer may point at. A printer's host is typed in by a user
with the printer write permission, and status queries and test prints then
open connections to it and show what came back, so it must name a printer
on the network: a host name or an IP address, never the stack's own
services or an address of the server itself. No I/O.
"""

import re

from src.modules.platform.domain.services.stack_hosts import is_always_refused_address
from src.modules.platform.domain.services.stack_hosts import is_stack_host
from src.modules.platform.domain.services.stack_hosts import parse_address

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_MAX_NAME_LENGTH = 253


def printer_host_problem(host: str) -> str | None:
    """Why `host` cannot be a printer's host, or None when it can. Where a
    host name leads is checked when a connection is opened
    (guarded_printer_gateway.py)."""
    value = host.strip()
    try:
        ip = parse_address(value)
    except ValueError:
        ip = None
    if ip is not None:
        if is_always_refused_address(ip):
            return f"{value} is not an address a printer can have."
        return None
    name = value.rstrip(".").lower()
    if (
        not name
        or len(name) > _MAX_NAME_LENGTH
        or not all(_LABEL.match(p) for p in name.split("."))
    ):
        return f"{host!r} is not a host name or IP address."
    if is_stack_host(name):
        return f"{value} is a service of the Glados stack, not a printer."
    return None
