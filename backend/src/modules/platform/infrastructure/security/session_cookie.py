"""
The httponly cookie carrying the web session token, the browser-visible
half of the login flow (see auth_deps.py's module docstring for the
cookie-vs-bearer and CSRF design this supports). Keeping the token in
this cookie rather than in localStorage is the whole point: JavaScript can
neither read nor persist it, so an XSS payload has nothing to exfiltrate.

Shaped like trusted_device.py's cookie: httponly always, Secure unless
debug (plain-http dev). Unlike the trusted-device cookie this one is not
path-scoped to /api/v1/auth, session auth is needed on the web surface
too, so it is scoped to the whole app instead.
"""

from fastapi import Response

from src.modules.platform.infrastructure.config.settings import cfg

SESSION_COOKIE = "glados_session"


def set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="strict",
        secure=not cfg.debug,
    )


def clear_session_cookie(response: Response) -> None:
    """Same attributes as set_session_cookie (minus the value/max_age):
    a browser matches a cookie to delete by name, path and domain, not by
    value, but repeating the other attributes here is what makes
    Starlette's own SameSite/Secure defaults not silently diverge from
    the cookie actually set."""
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=not cfg.debug,
    )
