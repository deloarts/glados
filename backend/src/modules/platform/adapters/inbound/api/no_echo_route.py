"""
Route class that removes the submitted values from request validation
errors. FastAPI's 422 body repeats every failing value under `input`, and
for a missing field the whole submitted body, so a typo next to a password
field would send the password back in the response, into browser
developer tools, proxies and error trackers. Routers that accept a
password use this class; the error locations, types and messages stay, so
the client can still tell which field is wrong.
"""

from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import Response

_ECHOING_KEYS = frozenset({"input", "ctx", "url"})


def _without_input(error: Any) -> Any:
    if not isinstance(error, dict):
        return error
    return {key: value for key, value in error.items() if key not in _ECHOING_KEYS}


class NoInputEchoRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as exc:
                raise RequestValidationError(
                    [_without_input(error) for error in exc.errors()]
                ) from None

        return route_handler
