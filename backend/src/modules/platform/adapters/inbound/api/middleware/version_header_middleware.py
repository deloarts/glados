"""
Pure-ASGI middleware that adds `X-Glados-Version` to every response on the
`pat` surface, error responses included.

An external client such as the SolidWorks add-in reads the backend version
from whichever call it makes, and can tell from a 401 or a 404 that the
backend it reached is newer or older than the one it was built for. Only
the `pat` prefix carries it: the web frontend checks the version through
`/health`, and the other surfaces have no use for it.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from src.modules.platform.const import API_KEY
from src.modules.platform.const import API_PAT
from src.modules.platform.const import API_PUBLIC
from src.modules.platform.const import VERSION
from src.modules.platform.const import VERSION_HEADER

# The surfaces the pat snapshot bundles, which external clients such as the
# SolidWorks add-in call and read the server version from.
_CONTRACT_PREFIXES = (API_PAT, API_KEY, API_PUBLIC)


def _is_pat_path(path: str) -> bool:
    """Whether the path is on one of the contract surfaces."""
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in _CONTRACT_PREFIXES)


class VersionHeaderMiddleware:
    def __init__(self, app: ASGIApp, version: str = VERSION) -> None:
        self._app = app
        self._version = version

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _is_pat_path(scope.get("path", "")):
            await self._app(scope, receive, send)
            return

        async def send_with_version(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if VERSION_HEADER not in headers:
                    headers.append(VERSION_HEADER, self._version)
            await send(message)

        await self._app(scope, receive, send_with_version)
