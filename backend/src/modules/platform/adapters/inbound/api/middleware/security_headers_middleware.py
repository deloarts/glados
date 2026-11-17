"""
Pure-ASGI middleware, modelled on RequestContextMiddleware, that adds a
handful of browser-side hardening headers to every response. This is a
cheap, correct backstop even with nothing in front of the app. Covers every
response the app produces, including the authenticated file-download
routes (user-uploaded bytes are served from the API origin, so the
MIME-sniffing/framing/cross-origin headers below matter) and error responses, since it sits outside
routing and exception handling.

Deliberately conservative:
  - Never overrides a header a downstream layer already set, a reverse
    proxy that already sends these must win. See _set_if_absent.
  - HSTS is sent only when the request arrived over HTTPS (directly or via
    a trusted X-Forwarded-Proto), since browsers ignore it over plain HTTP
    and it must not poison dev/http://localhost.
  - Every response gets `Content-Security-Policy: default-src 'none';
    frame-ancestors 'none'`. The API serves data and files, never a page
    that loads anything, so a response a browser does open as a document,
    such as an uploaded file, can run no script, load nothing and sit in no
    frame. Two kinds of response get less. The Swagger UI pages under /docs
    (docs.py) load their script and styles from a CDN and run an inline
    script, so they get no policy from here. A PDF gets only
    `frame-ancestors 'none'`, because a browser's built-in PDF viewer runs
    inside the document and `default-src 'none'` can stop it; a PDF runs no
    script on the Glados origin either way.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

_STATIC_HEADERS: tuple[tuple[str, str], ...] = (
    # Stops a browser from MIME-sniffing a response into executable
    # content. Unconditional; highest value here given the download routes
    # serve user-uploaded files.
    ("x-content-type-options", "nosniff"),
    # An API plus authenticated file downloads: nothing here is meant to
    # be embedded in another site's frame.
    ("x-frame-options", "DENY"),
    ("referrer-policy", "strict-origin-when-cross-origin"),
    # Stops another origin's <img>/<script> tag from loading a downloaded
    # file cross-site.
    ("cross-origin-resource-policy", "same-site"),
)

_HSTS_HEADER = ("strict-transport-security", "max-age=31536000; includeSubDomains")

_CSP = "content-security-policy"
_API_CSP = "default-src 'none'; frame-ancestors 'none'"
_PDF_CSP = "frame-ancestors 'none'"
_DOCS_PATH = "/docs"


def _csp_for(path: str, content_type: str) -> str | None:
    """The policy a response gets, None for the Swagger UI pages."""
    if path == _DOCS_PATH or path.startswith(f"{_DOCS_PATH}/"):
        return None
    if content_type.split(";", 1)[0].strip().lower() == "application/pdf":
        return _PDF_CSP
    return _API_CSP


def _is_https(scope: Scope) -> bool:
    if scope.get("scheme") == "https":
        return True
    headers: dict[bytes, bytes] = dict(scope.get("headers", []))
    forwarded_proto = headers.get(b"x-forwarded-proto", b"").decode().lower()
    return forwarded_proto == "https"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        https = _is_https(scope)
        path: str = scope.get("path", "")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                mutable = MutableHeaders(scope=message)
                for name, value in _STATIC_HEADERS:
                    _set_if_absent(mutable, name, value)
                if https:
                    _set_if_absent(mutable, *_HSTS_HEADER)
                csp = _csp_for(path, mutable.get("content-type", ""))
                if csp is not None:
                    _set_if_absent(mutable, _CSP, csp)
            await send(message)

        await self._app(scope, receive, send_with_headers)


def _set_if_absent(headers: MutableHeaders, name: str, value: str) -> None:
    """A reverse proxy, or the endpoint itself, that already set this
    header must win. Never duplicate or override it."""
    if name not in headers:
        headers.append(name, value)
