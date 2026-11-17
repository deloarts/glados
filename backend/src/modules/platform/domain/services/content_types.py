"""The content type a stored file is served as, and whether a browser may
show it inline.

The type comes from the stored file's extension alone, never from what an
uploading client claimed. A client can label a STEP file `text/html`, and a
browser handed that type renders the bytes as a page that runs script on
the Glados origin. Every upload therefore stores the type named here for its
extension, and every link to a stored file repeats it, so the served type
never depends on the metadata the storage backend holds.

Only the types in INLINE_SAFE_CONTENT_TYPES may open in a browser tab:
raster images and PDF carry nothing a browser runs on the page's origin.
Everything else, SVG and HTML included, is offered as a download.
"""

from types import MappingProxyType
from urllib.parse import quote

OCTET_STREAM = "application/octet-stream"
PDF = "application/pdf"
SVG = "image/svg+xml"

# Every extension a stored upload can carry. DXF uses `application/dxf`
# rather than the registered `image/vnd.dxf`, because the frontend previews
# any `image/*` file as a picture.
CONTENT_TYPES_BY_EXTENSION = MappingProxyType(
    {
        ".pdf": PDF,
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".ico": "image/x-icon",
        ".svg": SVG,
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".stl": "model/stl",
        ".3mf": "model/3mf",
        ".step": "model/step",
        ".stp": "model/step",
        ".dxf": "application/dxf",
    }
)

INLINE_SAFE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif", PDF})


def content_type_for(file_name: str) -> str:
    """The content type for a file name, a storage key or a bare extension
    such as ".step", by its last extension regardless of case. A name
    without a known extension is an opaque byte stream."""
    _, dot, extension = file_name.rsplit("/", 1)[-1].rpartition(".")
    if not dot:
        return OCTET_STREAM
    return CONTENT_TYPES_BY_EXTENSION.get(f".{extension.lower()}", OCTET_STREAM)


def is_inline_safe(content_type: str) -> bool:
    """Whether a browser may render this type in a tab instead of saving it.
    Parameters such as `; charset=` are ignored."""
    return content_type.split(";", 1)[0].strip().lower() in INLINE_SAFE_CONTENT_TYPES


def content_disposition(file_name: str, *, inline: bool) -> str:
    """A Content-Disposition value naming `file_name`, inline or as an
    attachment. CR and LF are removed so a crafted name cannot add a header,
    and the name is given twice: as a plain ASCII `filename` for old clients
    and as the RFC 5987 encoded `filename*` that keeps non-ASCII characters
    (RFC 6266)."""
    safe_name = file_name.replace("\r", "").replace("\n", "") or "download"
    ascii_fallback = (
        safe_name.encode("ascii", "replace").decode("ascii").replace('"', "'").replace("\\", "_")
    )
    encoded = quote(safe_name, safe="")
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
