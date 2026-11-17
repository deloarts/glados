"""tests/unit/eplan_data_portal/test_client.py: the httpx client against a
mocked transport (headers, error mapping, batching, the picture download)."""

import httpx
import pytest

from src.modules.external_data.adapters.outbound.external.eplan_data_portal.client import (
    HttpxEplanDataPortal,
)
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.client import (
    site_url_of,
)
from src.modules.external_data.domain.errors import EdpAuthenticationFailedError
from src.modules.external_data.domain.errors import EdpProviderError
from src.modules.external_data.domain.errors import EdpUnavailableError
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from tests.unit.eplan_data_portal._documents import BASE_URL
from tests.unit.eplan_data_portal._documents import PICTURE_URL
from tests.unit.eplan_data_portal._documents import check_document
from tests.unit.eplan_data_portal._documents import parts_document

CONNECTION = EdpConnection(base_url=BASE_URL, pat="secret-token")


def _portal(handler) -> HttpxEplanDataPortal:  # type: ignore[no-untyped-def]
    return HttpxEplanDataPortal(CONNECTION, transport=httpx.MockTransport(handler))


def test_edp_site_url_drops_the_api_path() -> None:
    assert site_url_of("https://portal.example.test/api/") == "https://portal.example.test"


def test_edp_connection_repr_hides_the_token() -> None:
    assert "secret-token" not in repr(CONNECTION)


async def test_edp_requests_carry_the_pat_and_parse_the_parts() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=parts_document(451627))

    parts = await _portal(handler).get_parts([451627])

    assert [p.part_id for p in parts] == [451627]
    request = seen[0]
    assert request.headers["Authorization"] == "Bearer PAT:secret-token"
    assert request.method == "POST"
    assert request.url.path == "/api/parts"
    assert request.content == b"451627"
    assert "picture_file.preview" in request.url.params["include"]


async def test_edp_check_numbers_sends_one_number_per_line() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(200, json=check_document())

    matches = await _portal(handler).check_numbers(["3RT2015-1BB41", " ", "6ES7"])

    assert bodies == [b"3RT2015-1BB41\n6ES7"]
    assert [m.part_ids for m in matches] == [(451627,), (), ()]


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, EdpAuthenticationFailedError),
        (403, EdpAuthenticationFailedError),
        (500, EdpProviderError),
    ],
)
async def test_edp_maps_http_errors(status: int, error: type[Exception]) -> None:
    portal = _portal(lambda request: httpx.Response(status, text="nope"))

    with pytest.raises(error) as raised:
        await portal.test_connection()

    assert "secret-token" not in str(raised.value)


async def test_edp_maps_a_transport_failure_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(EdpUnavailableError):
        await _portal(handler).search("3RT2015", 5)


async def test_edp_picture_is_fetched_without_the_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"\x89PNG")

    picture = await _portal(handler).fetch_picture(PICTURE_URL)

    assert picture == b"\x89PNG"
    assert "Authorization" not in seen[0].headers


async def test_edp_picture_refuses_a_non_https_url() -> None:
    portal = _portal(lambda request: httpx.Response(200, content=b"x"))

    assert await portal.fetch_picture("http://blob.example.test/a.png") is None
