"""
Abstract file storage interface. Application layer calls this, never a
concrete SDK directly.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings


@dataclass(frozen=True)
class StoredObjectStream:
    """An opened stored object, read chunk by chunk. `chunks` closes the
    underlying file or connection when it is exhausted or closed early."""

    content_type: str
    size: int | None
    chunks: AsyncIterator[bytes]


@dataclass(frozen=True)
class StoredObjectInfo:
    """A stored object's key and when it was last written, aware UTC."""

    key: str
    last_modified: datetime


@runtime_checkable
class IStoragePort(Protocol):
    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        """Write bytes to the store under the given key."""
        ...

    async def download(self, key: str) -> tuple[bytes, str]:
        """Return (data, content_type) for the object at key."""
        ...

    async def open_stream(self, key: str) -> StoredObjectStream:
        """Open the object at key for chunked reading, for objects too large
        to hold in memory (backup archives). Raises the same errors as
        `download` when the key does not exist, before any byte is read."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object at key. No-op if the key does not exist."""
        ...

    async def list_keys(self, prefix: str = "") -> list[str]:
        """Return all object keys, optionally filtered by prefix."""
        ...

    async def list_objects(self, prefix: str) -> list[StoredObjectInfo]:
        """Return every object under the prefix with the time it was last
        written, for sweeps that remove blobs no row names any more."""
        ...

    def get_url(self, key: str, file_name: str | None = None) -> str:
        """Return a URL (presigned or static) valid for at least 1 hour. The
        response it yields carries the content type of the key's extension
        and opens inline only for an inline-safe type, otherwise it downloads
        as `file_name` (the key's last segment when None); see
        content_types.py."""
        ...

    async def test_connection(self) -> None:
        """Raise an exception if the backend is unreachable or misconfigured."""
        ...


@runtime_checkable
class IStorageAdapterFactory(Protocol):
    def __call__(self, settings: AdminStorageSettings) -> IStoragePort:
        """Build the IStoragePort implementation for the given settings.

        A factory port rather than a single injected IStoragePort because some
        callers (storage migration, connection testing) need to build an
        adapter from settings that are not yet the persisted/active ones.
        """
        ...
