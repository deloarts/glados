"""
Shared response-header building for routes that serve user-uploaded bytes
directly from the API origin (item-attachment downloads, admin backup
archives). Centralizes the hardening every such route needs:

- `X-Content-Type-Options: nosniff`: the browser must not guess a
  friendlier content type than the one we declare.
- A safe `Content-Disposition`: CRLF is stripped from the caller-supplied
  file name (header-injection guard), and both the plain `filename=` and
  the RFC 5987 `filename*=` forms are emitted so non-ASCII names survive.
- `disposition="inline"` is honoured only for the types
  `content_types.INLINE_SAFE_CONTENT_TYPES` lists as safe to render in a
  browser tab (raster images, PDF); everything else
  (notably `text/html` and `image/svg+xml`, which a browser will happily
  execute if served inline from the API's own origin) is forced to
  `attachment` regardless of what the caller asked for. Serving
  user-uploaded bytes from the API origin instead of a separate static
  mount is a new stored-XSS surface; this allowlist is the mitigation.
- `Cache-Control: private, max-age=3600`, matching the existing avatar
  route (`users.py`'s `read_user_avatar`).

`file_download_response` wraps those headers around in-memory bytes, and
`read_upload` reads a multipart upload with the file name and content type
fallbacks every upload route applies.
"""

from fastapi import Response
from fastapi import UploadFile

from src.modules.platform.domain.services.content_types import content_disposition
from src.modules.platform.domain.services.content_types import is_inline_safe


def build_download_headers(
    file_name: str, *, content_type: str, disposition: str = "attachment"
) -> dict[str, str]:
    """Build the header set for a byte-serving download/preview response.

    `disposition` is whatever the caller (typically a `?disposition=`
    query param) asked for; it is only honoured as `"inline"` when
    `content_type` is in the inline-safe allowlist, otherwise the response
    is always `attachment`.
    """
    inline = disposition == "inline" and is_inline_safe(content_type)
    return {
        "Content-Disposition": content_disposition(file_name, inline=inline),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
    }


def file_download_response(
    data: bytes, file_name: str, *, content_type: str, disposition: str = "attachment"
) -> Response:
    """A response serving `data` with the hardened download headers above."""
    headers = build_download_headers(file_name, content_type=content_type, disposition=disposition)
    return Response(content=data, media_type=content_type, headers=headers)


async def read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """The uploaded bytes, file name and content type. A part without a
    file name falls back to its `filename` header and then to "upload",
    and one without a content type is treated as an opaque byte stream."""
    data = await file.read()
    file_name = file.filename or file.headers.get("filename", "upload")
    content_type = file.content_type or "application/octet-stream"
    return data, file_name, content_type
