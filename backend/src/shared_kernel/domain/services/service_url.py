"""The URL rule for a service in the same stack that Glados calls with an API
key, such as the time tracking service or the stock service.

Plain http is accepted, because such a service publishes no port outside
the stack's network. The URL still must not carry anything a redirect
could abuse, so user information, a query and a fragment are refused.
"""

from urllib.parse import urlsplit


def assert_plain_http_url(value: str, field: str) -> str:
    """Returns the trimmed URL without a trailing slash. Raises ValueError
    unless it is an absolute http(s) URL with a host and no user info,
    query or fragment."""
    trimmed = value.strip()
    parts = urlsplit(trimmed)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError(f"{field} must start with http:// or https://.")
    if not parts.hostname:
        raise ValueError(f"{field} must name a host.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise ValueError(f"{field} must not contain user information.")
    if parts.query or parts.fragment or "?" in trimmed or "#" in trimmed:
        raise ValueError(f"{field} must not contain a query or fragment.")
    try:
        _ = parts.port
    except ValueError as exc:
        raise ValueError(f"{field} has an invalid port.") from exc
    return trimmed.rstrip("/")


def normalize_service_url(value: str) -> str:
    """A service URL as stored. Empty means not configured."""
    if not value.strip():
        return ""
    return assert_plain_http_url(value, "service_url")
