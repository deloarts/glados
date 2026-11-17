"""
S3-compatible object storage adapter using boto3.
Handles self-hosted S3-compatible servers such as SeaweedFS (endpoint_url
provided) as well as AWS S3 (endpoint_url omitted).
boto3 is imported lazily so the app starts cleanly when provider is "local".

Connect and read timeouts are explicit rather than botocore's 60s defaults
with legacy retries, so an unreachable endpoint fails a request in seconds.
The read timeout bounds a single socket read, not a whole transfer, so large
uploads and downloads are unaffected.

boto3 has no async client, so the async port methods run the SDK calls on a
worker thread.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from anyio import to_thread

from src.modules.platform.adapters.outbound.external.storage.chunked_read import CHUNK_SIZE
from src.modules.platform.adapters.outbound.external.storage.chunked_read import iterate_in_thread
from src.modules.platform.domain.services.content_types import content_disposition
from src.modules.platform.domain.services.content_types import content_type_for
from src.modules.platform.domain.services.content_types import is_inline_safe
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import StoredObjectInfo
from src.modules.platform.ports.outbound.storage_port import StoredObjectStream

_CONNECT_TIMEOUT_SECONDS = 5
_READ_TIMEOUT_SECONDS = 30
_MAX_ATTEMPTS = 3


class S3StorageAdapter:
    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str | None,
        endpoint_url: str | None,
        use_ssl: bool,
        public_endpoint_url: str | None = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        kwargs: dict[str, Any] = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "use_ssl": use_ssl,
            "config": Config(
                # Presigned URLs carry response-content-* overrides, which
                # botocore would otherwise sign with SigV2, and S3-compatible
                # stores such as SeaweedFS refuse SigV2 signatures.
                signature_version="s3v4",
                connect_timeout=_CONNECT_TIMEOUT_SECONDS,
                read_timeout=_READ_TIMEOUT_SECONDS,
                retries={"total_max_attempts": _MAX_ATTEMPTS, "mode": "standard"},
            ),
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if region:
            kwargs["region_name"] = region

        self._bucket = bucket
        self._client = boto3.client("s3", **kwargs)

        if public_endpoint_url:
            presign_kwargs = {**kwargs, "endpoint_url": public_endpoint_url}
            self._presign_client = boto3.client("s3", **presign_kwargs)
        else:
            self._presign_client = self._client

        log.debug(
            "S3StorageAdapter initialized: bucket=%r, endpoint=%r, region=%r.",
            bucket,
            endpoint_url,
            region,
        )

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await to_thread.run_sync(self._upload_blocking, key, data, content_type)

    def _upload_blocking(self, key: str, data: bytes, content_type: str) -> None:
        log.debug(
            "S3: uploading %r (%s bytes, %s) to bucket %r.",
            key,
            len(data),
            content_type,
            self._bucket,
        )
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        log.debug("S3: upload complete for %r.", key)

    async def download(self, key: str) -> tuple[bytes, str]:
        return await to_thread.run_sync(self._download_blocking, key)

    def _download_blocking(self, key: str) -> tuple[bytes, str]:
        log.debug("S3: downloading %r from bucket %r.", key, self._bucket)
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        data: bytes = response["Body"].read()
        content_type: str = response.get("ContentType", "application/octet-stream")
        log.debug("S3: downloaded %r (%s bytes).", key, len(data))
        return data, content_type

    async def open_stream(self, key: str) -> StoredObjectStream:
        response = await to_thread.run_sync(
            lambda: self._client.get_object(Bucket=self._bucket, Key=key)
        )
        body = response["Body"]
        return StoredObjectStream(
            content_type=response.get("ContentType", "application/octet-stream"),
            size=response.get("ContentLength"),
            chunks=iterate_in_thread(lambda: body.read(CHUNK_SIZE), body.close),
        )

    async def delete(self, key: str) -> None:
        await to_thread.run_sync(self._delete_blocking, key)

    def _delete_blocking(self, key: str) -> None:
        log.debug("S3: deleting %r from bucket %r.", key, self._bucket)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    async def list_keys(self, prefix: str = "") -> list[str]:
        return await to_thread.run_sync(self._list_keys_blocking, prefix)

    def _list_keys_blocking(self, prefix: str = "") -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        log.debug("S3: listed %s keys under prefix %r.", len(keys), prefix)
        return keys

    async def list_objects(self, prefix: str) -> list[StoredObjectInfo]:
        return await to_thread.run_sync(self._list_objects_blocking, prefix)

    def _list_objects_blocking(self, prefix: str) -> list[StoredObjectInfo]:
        objects: list[StoredObjectInfo] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects.extend(
                StoredObjectInfo(obj["Key"], obj["LastModified"])
                for obj in page.get("Contents", [])
            )
        return objects

    async def test_connection(self) -> None:
        await to_thread.run_sync(self._test_connection_blocking)

    def _test_connection_blocking(self) -> None:
        log.debug("S3: testing connection to bucket %r.", self._bucket)
        self._client.head_bucket(Bucket=self._bucket)
        log.info("S3: connection to bucket %r OK.", self._bucket)

    def get_url(self, key: str, file_name: str | None = None) -> str:
        """A presigned GET valid for an hour. The signed response overrides
        set the content type from the key's extension and the disposition
        from the inline-safe list, so an object stored with a client's
        claimed type, before uploads stopped keeping it, is served safely
        too."""
        content_type = content_type_for(key)
        url: str = self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": content_disposition(
                    file_name or PurePosixPath(key).name, inline=is_inline_safe(content_type)
                ),
            },
            ExpiresIn=3600,
        )
        return url
