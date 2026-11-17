"""
Azure Blob Storage adapter using azure-storage-blob.
SDK is imported lazily so the app starts cleanly when provider is not "azure".

Connection and read timeouts are explicit instead of the SDK defaults, so an
unreachable account fails a request in seconds. The read timeout bounds a
single socket read, not a whole transfer.

The async port methods run the sync SDK calls on a worker thread.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from anyio import to_thread

from src.modules.platform.adapters.outbound.external.storage.chunked_read import iterate_in_thread
from src.modules.platform.domain.services.content_types import content_disposition
from src.modules.platform.domain.services.content_types import content_type_for
from src.modules.platform.domain.services.content_types import is_inline_safe
from src.modules.platform.ports.outbound.storage_port import StoredObjectInfo
from src.modules.platform.ports.outbound.storage_port import StoredObjectStream

_CONNECTION_TIMEOUT_SECONDS = 5
_READ_TIMEOUT_SECONDS = 30


class AzureStorageAdapter:
    def __init__(
        self,
        container: str,
        account_name: str,
        account_key: str,
        endpoint_url: str | None,
    ) -> None:
        from azure.storage.blob import BlobServiceClient

        account_url = endpoint_url or f"https://{account_name}.blob.core.windows.net"
        self._service = BlobServiceClient(
            account_url=account_url,
            credential=account_key,
            connection_timeout=_CONNECTION_TIMEOUT_SECONDS,
            read_timeout=_READ_TIMEOUT_SECONDS,
        )
        self._container = container
        self._account_name = account_name
        self._account_key = account_key

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await to_thread.run_sync(self._upload_blocking, key, data, content_type)

    def _upload_blocking(self, key: str, data: bytes, content_type: str) -> None:
        from azure.storage.blob import ContentSettings

        blob = self._service.get_blob_client(container=self._container, blob=key)
        blob.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    async def download(self, key: str) -> tuple[bytes, str]:
        return await to_thread.run_sync(self._download_blocking, key)

    def _download_blocking(self, key: str) -> tuple[bytes, str]:
        blob = self._service.get_blob_client(container=self._container, blob=key)
        data: bytes = blob.download_blob().readall()
        props = blob.get_blob_properties()
        content_type: str = props.content_settings.content_type or "application/octet-stream"
        return data, content_type

    async def open_stream(self, key: str) -> StoredObjectStream:
        blob = self._service.get_blob_client(container=self._container, blob=key)
        downloader = await to_thread.run_sync(blob.download_blob)
        chunks = downloader.chunks()
        return StoredObjectStream(
            content_type=downloader.properties.content_settings.content_type
            or "application/octet-stream",
            size=downloader.size,
            chunks=iterate_in_thread(lambda: next(chunks, b""), lambda: None),
        )

    async def delete(self, key: str) -> None:
        await to_thread.run_sync(self._delete_blocking, key)

    def _delete_blocking(self, key: str) -> None:
        blob = self._service.get_blob_client(container=self._container, blob=key)
        blob.delete_blob(delete_snapshots="include")

    async def list_keys(self, prefix: str = "") -> list[str]:
        return await to_thread.run_sync(self._list_keys_blocking, prefix)

    def _list_keys_blocking(self, prefix: str = "") -> list[str]:
        container = self._service.get_container_client(self._container)
        return [b.name for b in container.list_blobs(name_starts_with=prefix or None)]

    async def list_objects(self, prefix: str) -> list[StoredObjectInfo]:
        return await to_thread.run_sync(self._list_objects_blocking, prefix)

    def _list_objects_blocking(self, prefix: str) -> list[StoredObjectInfo]:
        container = self._service.get_container_client(self._container)
        return [
            StoredObjectInfo(blob.name, blob.last_modified)
            for blob in container.list_blobs(name_starts_with=prefix or None)
        ]

    async def test_connection(self) -> None:
        await to_thread.run_sync(self._test_connection_blocking)

    def _test_connection_blocking(self) -> None:
        self._service.get_container_client(self._container).get_container_properties()

    def get_url(self, key: str, file_name: str | None = None) -> str:
        """A read SAS valid for an hour. Like the S3 adapter, the SAS sets
        the response content type from the key's extension and the
        disposition from the inline-safe list."""
        from datetime import UTC
        from datetime import datetime
        from datetime import timedelta

        from azure.storage.blob import BlobSasPermissions
        from azure.storage.blob import generate_blob_sas

        content_type = content_type_for(key)
        sas = generate_blob_sas(
            account_name=self._account_name,
            container_name=self._container,
            blob_name=key,
            account_key=self._account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(UTC) + timedelta(hours=1),
            content_type=content_type,
            content_disposition=content_disposition(
                file_name or PurePosixPath(key).name, inline=is_inline_safe(content_type)
            ),
        )
        return f"https://{self._account_name}.blob.core.windows.net/{self._container}/{key}?{sas}"
