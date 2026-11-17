"""
A FastAPI dependency that rejects an oversized upload from its
`Content-Length` header, BEFORE the endpoint does `await file.read()` and
pulls the whole body into memory. Per-category size limits still apply in
the use cases (they validate the actual decoded bytes); this is the coarse
front-door guard against a multi-GB body being buffered just to be
rejected. See const.MAX_UPLOAD_BYTES.

Not a substitute for a reverse-proxy body cap in production, a client can
lie about Content-Length or omit it, but it closes the common case at the
application layer at zero cost.
"""

from collections.abc import Callable

from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from src.modules.platform.const import MAX_UPLOAD_BYTES

# Room for the multipart envelope (boundaries, part headers, other form
# fields) on top of the file itself, so a file exactly at its limit passes.
_MULTIPART_OVERHEAD_BYTES = 1024 * 1024


def max_upload_size(limit_bytes: int) -> Callable[[Request], None]:
    """A dependency rejecting a request whose declared body is larger than a
    file of `limit_bytes` plus multipart overhead. Endpoints with a small
    per-file limit use this so their body is never buffered far beyond it.

    A missing/malformed Content-Length is allowed through, the use-case
    size checks remain the backstop for those, since the goal here is only
    to cheaply reject the honestly-declared oversized request."""
    ceiling = limit_bytes + _MULTIPART_OVERHEAD_BYTES

    def enforce(request: Request) -> None:
        raw = request.headers.get("content-length")
        if raw is None:
            return
        try:
            declared = int(raw)
        except ValueError:
            return
        if declared > ceiling:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Upload exceeds the maximum allowed size of {ceiling} bytes.",
            )

    return enforce


# The app-wide ceiling, for endpoints whose per-file limits go up to the
# largest category (see const.MAX_UPLOAD_BYTES).
enforce_max_upload_size = max_upload_size(MAX_UPLOAD_BYTES - _MULTIPART_OVERHEAD_BYTES)
