"""
Shared helpers for the upload/delete-a-stored-asset use cases (branding
images, login video, user avatars, bought-item/order files). Each use
case still owns its own entity lookup, permission check, and save,
only the mechanical parts (size/type validation, extension resolution,
best-effort storage calls, and the commit, upload and cleanup order of a
replacement) are shared here.
"""

import mimetypes
from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.domain.exceptions import StoragePublicUrlUnavailableError
from src.modules.platform.domain.services.content_types import content_type_for
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def assert_within_size_limit(
    data: bytes, max_bytes: int, *, error: type[Exception], label: str
) -> None:
    if len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise error(f"{label} must be ≤ {mb} MB (got {len(data)} bytes).")


def assert_allowed_type(
    content_type: str,
    allowed_types: set[str] | dict[str, str],
    *,
    error: type[Exception],
    label: str,
) -> None:
    if content_type not in allowed_types:
        raise error(
            f"Unsupported {label} type {content_type!r}. "
            f"Allowed: {', '.join(sorted(allowed_types))}."
        )


def _is_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(data: bytes) -> bool:
    return data.startswith(b"\xff\xd8\xff")


def _is_gif(data: bytes) -> bool:
    return data[:6] in (b"GIF87a", b"GIF89a")


def _is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _is_ico(data: bytes) -> bool:
    return data[:4] == b"\x00\x00\x01\x00"


def _is_svg(data: bytes) -> bool:
    """SVG is XML text, not a binary format, so it has no fixed magic
    number the way the other registered types do. Sniffing for an `<svg`
    tag within the first kilobyte, after lowercasing, tolerates a
    leading BOM, XML prolog, DOCTYPE, or comment while still rejecting
    content that is not SVG at all.
    """
    return b"<svg" in data[:1024].lower()


def _is_mp4(data: bytes) -> bool:
    return len(data) >= 8 and data[4:8] == b"ftyp"


def _is_webm(data: bytes) -> bool:
    return data.startswith(b"\x1a\x45\xdf\xa3")


# One entry per content type any upload use case declares as allowed, so a
# type missing here is a gap to close, not a silent pass-through. Keyed by
# the exact MIME string the endpoint receives (the same value
# assert_allowed_type checks against), never inferred from the file
# extension, which the client does not send.
_MAGIC_BYTE_CHECKS: dict[str, Callable[[bytes], bool]] = {
    "image/png": _is_png,
    "image/jpeg": _is_jpeg,
    "image/gif": _is_gif,
    "image/webp": _is_webp,
    "image/x-icon": _is_ico,
    "image/vnd.microsoft.icon": _is_ico,
    "image/svg+xml": _is_svg,
    "video/mp4": _is_mp4,
    "video/webm": _is_webm,
}


def assert_magic_bytes_match(
    data: bytes, content_type: str, *, error: type[Exception], label: str
) -> None:
    """Verify `data` actually starts with the byte signature expected of
    `content_type`. `assert_allowed_type` only checks the header the
    client declared, which is trivial to spoof, this catches a payload
    that does not match what it claims to be (e.g. an executable
    uploaded as `image/png`) before it reaches storage.

    A content type with no entry in `_MAGIC_BYTE_CHECKS` passes through
    unchecked rather than raising, so a caller adding a new allowed type
    must add its signature check here deliberately instead of this
    function silently blocking it.
    """
    check = _MAGIC_BYTE_CHECKS.get(content_type)
    if check is not None and not check(data):
        raise error(f"{label} content does not match its declared type {content_type!r}.")


def resolve_extension(content_type: str, overrides: dict[str, str] | None = None) -> str:
    if overrides and content_type in overrides:
        return overrides[content_type]
    return mimetypes.guess_extension(content_type) or ".bin"


async def delete_storage_object_best_effort(
    storage: IStoragePort, key: str, *, context: str
) -> None:
    """Best-effort delete of a superseded/removed storage object.
    Failures are logged, not raised, the DB state change (which key is
    current) is the source of truth; an orphaned blob is a cleanup
    concern, not a reason to fail the request.
    """
    try:
        await storage.delete(key)
    except Exception:
        log.warning("Failed to delete storage object %r (%s).", key, context, exc_info=True)


async def replace_stored_asset[T](
    storage: IStoragePort,
    uow: IUnitOfWork,
    *,
    key: str,
    old_key: str | None,
    data: bytes,
    save: Callable[[], Awaitable[T]],
    label: str,
) -> T:
    """Uploads `data` under `key` and points the owner at it through `save`,
    which writes the new key without committing.

    The caller has read the owner and written nothing yet, so its read
    transaction is committed first and no pooled connection idles during
    the upload. When the save or its commit fails, the new object is
    deleted again, unless `key` equals `old_key`: a same-key upload has
    already overwritten the object the stored row points at, and deleting
    it would leave the row pointing at nothing. The superseded object goes
    only once the new key is committed. `label` names the asset in the
    cleanup log contexts. The stored content type follows the extension of
    `key` (content_types.py).
    """
    await uow.commit()
    await storage.upload(key, data, content_type_for(key))
    try:
        saved = await save()
        await uow.commit()
    except Exception:
        if key != old_key:
            await delete_storage_object_best_effort(
                storage, key, context=f"discarding unsaved {label}"
            )
        raise
    if old_key and old_key != key:
        await delete_storage_object_best_effort(storage, old_key, context=f"replacing {label}")
    return saved


def get_storage_url_best_effort(
    storage: IStoragePort, path: str, *, context: str, file_name: str | None = None
) -> str | None:
    """Best-effort presigned/public URL lookup. Failures are logged, not
    raised, the file record was already saved; the URL is a convenience
    the client can re-fetch later.

    StoragePublicUrlUnavailableError is caught separately, ahead of the
    broad handler below: it is the expected, permanent outcome for every
    local-storage key (no `/media` mount serves local files, so local never
    has a public URL), not a failure worth a WARNING on every file in
    every request. The broad handler still warns for S3/Azure, where a
    caught exception means the backend is actually unreachable.

    `file_name` names the download the URL offers, see IStoragePort.get_url.
    """
    try:
        return storage.get_url(path, file_name)
    except StoragePublicUrlUnavailableError:
        return None
    except Exception:
        log.warning("Failed to get URL for storage object %r (%s).", path, context, exc_info=True)
        return None
