"""
The host names and addresses that reach the Glados stack itself, which no
outbound target an admin or user configures may use: localhost and the
service names of docker-compose.yml and docker-compose.dev.yml, which
Docker's DNS resolves inside the stack, and the addresses that are never
another host on the network.
"""

import ipaddress
from collections.abc import Sequence
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from ipaddress import IPv6Address
from ipaddress import IPv6Network

# is_unspecified covers 0.0.0.0 only, but Linux treats the whole block as
# the local host.
_THIS_NETWORK = IPv4Network("0.0.0.0/8")

# Plus time-tracking, the name the time tracking service runs under when it is
# deployed next to the stack.
STACK_SERVICE_NAMES = frozenset(
    {
        "backend",
        "frontend",
        "postgres",
        "redis",
        "seaweedfs",
        "pgadmin",
        "maintenance",
        "cloudflared",
        "time-tracking",
    }
)


def is_stack_host(host: str) -> bool:
    """Whether `host` is localhost or one of the stack's service names."""
    name = host.strip().rstrip(".").lower()
    return name == "localhost" or name.endswith(".localhost") or name in STACK_SERVICE_NAMES


def is_always_refused_address(
    ip: IPv4Address | IPv6Address,
    internal_subnets: Sequence[IPv4Network | IPv6Network] = (),
) -> bool:
    """Whether `ip` can never be an outbound target: loopback, link-local
    (which covers the 169.254.169.254 cloud metadata address), unspecified,
    the 0.0.0.0/8 "this network" block, multicast, reserved and IPv6 site
    local addresses, the IPv4-mapped IPv6 forms of all of these, and the
    subnets of the stack's own networks."""
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
        or (isinstance(ip, IPv4Address) and ip in _THIS_NETWORK)
        or (isinstance(ip, IPv6Address) and ip.is_site_local)
    ):
        return True
    return any(ip.version == net.version and ip in net for net in internal_subnets)


def parse_address(value: str) -> IPv4Address | IPv6Address:
    """`value` as an IP address, without an IPv6 zone suffix such as
    `%eth0`. Raises ValueError when it is not an address."""
    return ipaddress.ip_address(value.split("%", 1)[0])
