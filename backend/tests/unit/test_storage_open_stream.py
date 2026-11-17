"""
Chunked reads through IStoragePort.open_stream: every adapter yields the
object in chunks with its size and content type, and closes the underlying
handle whether the consumer reads to the end or stops early.
"""

from types import SimpleNamespace

import pytest

from src.modules.platform.adapters.outbound.external.storage.azure_storage import (
    AzureStorageAdapter,
)
from src.modules.platform.adapters.outbound.external.storage.local_storage import (
    LocalStorageAdapter,
)
from src.modules.platform.adapters.outbound.external.storage.s3_storage import S3StorageAdapter
from src.modules.platform.domain.exceptions import StoragePathError


@pytest.fixture(autouse=True)
def small_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("local_storage", "s3_storage"):
        monkeypatch.setattr(
            f"src.modules.platform.adapters.outbound.external.storage.{module}.CHUNK_SIZE",
            4,
            raising=True,
        )


async def _read_all(stream) -> list[bytes]:
    return [chunk async for chunk in stream.chunks]


async def test_local_stream_yields_chunks_with_size_and_type(tmp_path) -> None:
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "dump.sql.gz").write_bytes(b"0123456789")
    adapter = LocalStorageAdapter(base_dir=str(tmp_path))

    stream = await adapter.open_stream("db/dump.sql.gz")

    assert stream.size == 10
    assert stream.content_type == "application/sql"
    assert await _read_all(stream) == [b"0123", b"4567", b"89"]


async def test_local_stream_of_a_missing_key_raises_before_streaming(tmp_path) -> None:
    adapter = LocalStorageAdapter(base_dir=str(tmp_path))

    with pytest.raises(FileNotFoundError):
        await adapter.open_stream("db/missing.sql.gz")


async def test_local_stream_keeps_path_containment(tmp_path) -> None:
    adapter = LocalStorageAdapter(base_dir=str(tmp_path / "media"))

    with pytest.raises(StoragePathError):
        await adapter.open_stream("../.env")


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False

    def read(self, size: int) -> bytes:
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk

    def close(self) -> None:
        self.closed = True


def _s3_adapter(body: _Body) -> S3StorageAdapter:
    adapter = object.__new__(S3StorageAdapter)
    adapter._bucket = "bucket"  # type: ignore[attr-defined]
    adapter._client = SimpleNamespace(  # type: ignore[attr-defined]
        get_object=lambda Bucket, Key: {
            "Body": body,
            "ContentType": "application/gzip",
            "ContentLength": 6,
        }
    )
    return adapter


async def test_s3_stream_reads_the_body_in_chunks_and_closes_it() -> None:
    body = _Body(b"abcdef")

    stream = await _s3_adapter(body).open_stream("db/x.gz")

    assert (stream.size, stream.content_type) == (6, "application/gzip")
    assert await _read_all(stream) == [b"abcd", b"ef"]
    assert body.closed


async def test_s3_stream_closes_the_body_when_the_consumer_stops_early() -> None:
    body = _Body(b"abcdefgh")
    stream = await _s3_adapter(body).open_stream("db/x.gz")

    async for _chunk in stream.chunks:
        break
    await stream.chunks.aclose()  # type: ignore[attr-defined]

    assert body.closed


async def test_azure_stream_yields_the_downloader_chunks() -> None:
    downloader = SimpleNamespace(
        chunks=lambda: iter([b"ab", b"cd"]),
        size=4,
        properties=SimpleNamespace(content_settings=SimpleNamespace(content_type=None)),
    )
    adapter = object.__new__(AzureStorageAdapter)
    adapter._container = "c"  # type: ignore[attr-defined]
    adapter._service = SimpleNamespace(  # type: ignore[attr-defined]
        get_blob_client=lambda container, blob: SimpleNamespace(download_blob=lambda: downloader)
    )

    stream = await adapter.open_stream("db/x.gz")

    assert (stream.size, stream.content_type) == (4, "application/octet-stream")
    assert await _read_all(stream) == [b"ab", b"cd"]
