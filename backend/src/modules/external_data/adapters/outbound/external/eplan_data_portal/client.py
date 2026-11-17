"""
httpx-backed implementation of IEplanDataPortal against the public API of
the EPLAN Data Portal (the OpenAPI document is at <base_url>/doc). Read
only: nothing is ever written to the portal, the user's download list
included.

One instance owns one long-lived httpx.AsyncClient per connection. Every
request carries `Authorization: Bearer PAT:<token>`, the form the portal
documents for a personal access token. Redirects are never followed, so the
token cannot travel to another host. The picture download is the one
exception to the portal host: the picture URL points at the portal's blob
storage and is fetched without the token.

Batch calls send their numbers or ids as text/plain and are chunked, so one
spreadsheet of a few hundred rows stays a handful of requests. Errors:
transport failure or timeout is EdpUnavailableError, HTTP 401 or 403 is
EdpAuthenticationFailedError, anything else unexpected is EdpProviderError.
Nothing here logs headers, and no exception message carries the token.
"""

import logging
from typing import Any

import httpx

from src.modules.external_data.adapters.outbound.external.eplan_data_portal.parsing import (
    PART_INCLUDES,
)
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.parsing import (
    parse_number_matches,
)
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.parsing import (
    parse_parts,
)
from src.modules.external_data.domain.errors import EdpAuthenticationFailedError
from src.modules.external_data.domain.errors import EdpProviderError
from src.modules.external_data.domain.errors import EdpUnavailableError
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpConnectionInfo
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpNumberMatch
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection

TIMEOUT_SECONDS = 20.0
CHECK_CHUNK = 100
PARTS_CHUNK = 50
MAX_PICTURE_BYTES = 10 * 1024 * 1024
_JSON_API = "application/vnd.api+json"

for _noisy in ("httpx", "httpcore"):
    _logger = logging.getLogger(_noisy)
    if _logger.getEffectiveLevel() < logging.WARNING:
        _logger.setLevel(logging.WARNING)


def site_url_of(base_url: str) -> str:
    """The portal's web address, the API base URL without its /api path."""
    trimmed = base_url.rstrip("/")
    return trimmed[: -len("/api")] if trimmed.endswith("/api") else trimmed


def _chunks(values: list[Any], size: int) -> list[list[Any]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


class HttpxEplanDataPortal:
    """IEplanDataPortal for one connection; create_eplan_data_portal caches
    one instance per connection and shares it on the event loop."""

    def __init__(
        self, connection: EdpConnection, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._site_url = site_url_of(connection.base_url)
        self._client = httpx.AsyncClient(
            base_url=connection.base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer PAT:{connection.pat}", "Accept": _JSON_API},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        )
        # The picture lives on blob storage; it never sees the token.
        self._picture_client = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=False, transport=transport
        )

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._picture_client.aclose()

    async def test_connection(self) -> EdpConnectionInfo:
        await self._json("GET", "basketitems", params={"page[limit]": 1})
        return EdpConnectionInfo(authenticated=True)

    async def check_numbers(self, numbers: list[str]) -> list[EdpNumberMatch]:
        cleaned = [n.strip() for n in numbers]
        matches: list[EdpNumberMatch] = []
        for chunk in _chunks(cleaned, CHECK_CHUNK):
            searchable = [n for n in chunk if n]
            if not searchable:
                matches.extend(EdpNumberMatch(search=n) for n in chunk)
                continue
            document = await self._json(
                "POST",
                "partscheck",
                params={"allow_multiple_results": 1},
                content="\n".join(searchable),
            )
            matches.extend(parse_number_matches(document, chunk))
        return matches

    async def search(self, query: str, limit: int) -> list[EdpPart]:
        if not query.strip():
            return []
        document = await self._json(
            "GET", "parts", params={"search": query.strip()[:100], "page[limit]": limit}
        )
        ids = [p.part_id for p in parse_parts(document, self._site_url)]
        return await self.get_parts(ids)

    async def get_parts(self, part_ids: list[int]) -> list[EdpPart]:
        parts: list[EdpPart] = []
        for chunk in _chunks(list(dict.fromkeys(part_ids)), PARTS_CHUNK):
            document = await self._json(
                "POST",
                "parts",
                params={"include": PART_INCLUDES},
                content=",".join(str(i) for i in chunk),
            )
            by_id = {p.part_id: p for p in parse_parts(document, self._site_url)}
            parts.extend(by_id[i] for i in chunk if i in by_id)
        return parts

    async def fetch_picture(self, url: str) -> bytes | None:
        if not url.lower().startswith("https://"):
            return None
        try:
            response = await self._picture_client.get(url)
        except httpx.HTTPError as exc:
            raise EdpUnavailableError("The Data Portal picture could not be loaded.") from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200 or len(response.content) > MAX_PICTURE_BYTES:
            raise EdpProviderError(f"The Data Portal picture answered HTTP {response.status_code}.")
        return response.content

    async def _json(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "text/plain"} if content is not None else None
        try:
            response = await self._client.request(
                method, path, params=params, content=content, headers=headers
            )
        except httpx.HTTPError as exc:
            raise EdpUnavailableError("The EPLAN Data Portal could not be reached.") from exc
        if response.status_code in (401, 403):
            raise EdpAuthenticationFailedError(
                "The EPLAN Data Portal refused the personal access token."
            )
        if response.status_code != 200:
            raise EdpProviderError(f"The EPLAN Data Portal answered HTTP {response.status_code}.")
        try:
            document = response.json()
        except ValueError as exc:
            raise EdpProviderError("The EPLAN Data Portal sent no valid JSON.") from exc
        if not isinstance(document, dict):
            raise EdpProviderError("The EPLAN Data Portal sent an unexpected answer.")
        return document
