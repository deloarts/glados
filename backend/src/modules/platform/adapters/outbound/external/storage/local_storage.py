"""
Filesystem-backed storage adapter. Files are written to a local directory
and served only through the app's authenticated download routes, so there
is no public URL (see `get_url` below).

Every key is resolved through `_resolve()` before touching the filesystem.
Unlike S3/Azure, where a key is an opaque string and `..` is just part of
the name, `Path(base) / key` here is a real path join, and it escapes the
root in two distinct ways: `../` walks upwards, and an *absolute* key makes
pathlib discard the base entirely. Both are closed in one place rather than
per call site, so a new method cannot forget the check.

The async port methods run the blocking filesystem calls on a worker thread.
"""

from __future__ import annotations

import mimetypes
import os
from datetime import UTC
from datetime import datetime
from pathlib import Path

from anyio import to_thread

from src.modules.platform.adapters.outbound.external.storage.chunked_read import CHUNK_SIZE
from src.modules.platform.adapters.outbound.external.storage.chunked_read import iterate_in_thread
from src.modules.platform.domain.exceptions import StoragePathError
from src.modules.platform.domain.exceptions import StoragePublicUrlUnavailableError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import StoredObjectInfo
from src.modules.platform.ports.outbound.storage_port import StoredObjectStream


class LocalStorageAdapter:
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)

    def _resolve(self, key: str) -> Path:
        """Resolve `key` against the storage root, refusing anything that
        lands outside it.

        `.resolve()` collapses `..` segments and makes the comparison
        absolute; `is_relative_to` then rejects both traversal and absolute
        keys. Note the base is resolved too, otherwise a relative
        base_dir (the default is `./media`) would never compare equal.
        """
        base = self._base.resolve()
        target = (base / key).resolve()
        if target != base and not target.is_relative_to(base):
            # No log line here: StoragePathError is in
            # exception_handlers._LOG_ERROR, so domain_error_handler
            # already logs this at ERROR, and the message below already
            # names the offending key, so a second line here would just
            # double it without adding anything.
            raise StoragePathError(f"Storage key {key!r} resolves outside the storage root.")
        return target

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await to_thread.run_sync(self._upload_blocking, key, data, content_type)

    def _upload_blocking(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        log.debug("Local storage: uploaded %r (%s bytes, %s).", key, len(data), content_type)

    async def download(self, key: str) -> tuple[bytes, str]:
        return await to_thread.run_sync(self._download_blocking, key)

    def _download_blocking(self, key: str) -> tuple[bytes, str]:
        path = self._resolve(key)
        data = path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(path))
        log.debug("Local storage: downloaded %r (%s bytes).", key, len(data))
        return data, content_type or "application/octet-stream"

    async def open_stream(self, key: str) -> StoredObjectStream:
        path = self._resolve(key)
        handle = await to_thread.run_sync(path.open, "rb")
        size = os.fstat(handle.fileno()).st_size
        content_type, _ = mimetypes.guess_type(str(path))
        return StoredObjectStream(
            content_type=content_type or "application/octet-stream",
            size=size,
            chunks=iterate_in_thread(lambda: handle.read(CHUNK_SIZE), handle.close),
        )

    async def delete(self, key: str) -> None:
        await to_thread.run_sync(self._delete_blocking, key)

    def _delete_blocking(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)
        log.debug("Local storage: deleted %r.", key)

    async def list_keys(self, prefix: str = "") -> list[str]:
        return await to_thread.run_sync(self._list_keys_blocking, prefix)

    def _list_keys_blocking(self, prefix: str = "") -> list[str]:
        search_root = self._resolve(prefix) if prefix else self._base.resolve()
        if not search_root.exists():
            return []
        base = self._base.resolve()
        keys: list[str] = []
        for dirpath, _, filenames in os.walk(search_root):
            for filename in filenames:
                abs_path = Path(dirpath) / filename
                keys.append(str(abs_path.relative_to(base)))
        return keys

    async def list_objects(self, prefix: str) -> list[StoredObjectInfo]:
        return await to_thread.run_sync(self._list_objects_blocking, prefix)

    def _list_objects_blocking(self, prefix: str) -> list[StoredObjectInfo]:
        base = self._base.resolve()
        objects: list[StoredObjectInfo] = []
        for key in self._list_keys_blocking(prefix):
            modified = (base / key).stat().st_mtime
            objects.append(StoredObjectInfo(key, datetime.fromtimestamp(modified, tz=UTC)))
        return objects

    def get_url(self, key: str, file_name: str | None = None) -> str:
        """Local storage has no unauthenticated route to serve `key` from,
        so it never returns a URL. `_resolve()` still runs first so a traversal key
        raises StoragePathError rather than silently "succeeding" with an
        unavailable-URL error. The containment guarantee must hold
        regardless of which error a caller ends up seeing.
        """
        self._resolve(key)
        raise StoragePublicUrlUnavailableError(
            f"Local storage does not serve public URLs for {key!r}; "
            "use an authenticated download route instead."
        )

    async def test_connection(self) -> None:
        await to_thread.run_sync(self._test_connection_blocking)

    def _test_connection_blocking(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
