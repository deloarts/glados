"""
The error body every surface answers a refusal with (exception_handlers.py),
declared on the routers of the external contract, so the frozen pat
snapshot names the statuses a client has to handle besides 422.
"""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """`code` is the refusing error's class name, which a client branches
    on; a refusal of the HTTP layer itself, such as a missing token, carries
    only `detail`."""

    detail: str
    code: str | None = None


_DESCRIPTIONS = {
    401: "Not authenticated, or the token or key is invalid or expired.",
    403: "Authenticated, but the token or key lacks a permission or scope the request needs.",
    404: "The resource does not exist or is not visible to the caller.",
    409: "The request conflicts with the current state, such as a stale edit version.",
    413: "The request body or an uploaded file is too large.",
    429: "Too many requests; send it again later.",
    503: "Maintenance mode, or a lost database race; send it again later.",
}


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """The OpenAPI `responses` of a router for the given statuses."""
    return {s: {"model": ErrorResponse, "description": _DESCRIPTIONS[s]} for s in statuses}


# A route of the pat or key surface may answer any of these.
AUTHENTICATED_ERRORS = error_responses(401, 403, 404, 409, 413, 429, 503)
# The public surface needs no credential.
PUBLIC_ERRORS = error_responses(404, 429, 503)
