"""
Path-containment tests for LocalStorageAdapter: every key resolves
through `_resolve()`, which keeps it inside the storage root.

Without that containment, each of the four escape vectors below would let
the endpoint chain on top of the adapter (`restore_files` ->
`list_keys`/`download`/`upload`) copy arbitrary host files into a served
directory, including `.env`, i.e. the JWT signing key. These tests pin
each vector shut individually.

The absolute-key case is the subtle one: `Path("/media") / "/etc/passwd"`
returns `/etc/passwd`, because pathlib discards the left operand when the
right is absolute. A containment check that only looked for ".." would
miss it entirely.
"""

import pytest

from src.modules.platform.adapters.outbound.external.storage.local_storage import (
    LocalStorageAdapter,
)
from src.modules.platform.domain.exceptions import StoragePathError
from src.modules.platform.domain.exceptions import StoragePublicUrlUnavailableError


@pytest.fixture
def root(tmp_path):
    """A storage root with a sibling directory holding a secret, so an
    escape has something recognisable to reach."""
    (tmp_path / "media").mkdir()
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text("SECRET")
    return tmp_path


@pytest.fixture
def adapter(root):
    return LocalStorageAdapter(base_dir=str(root / "media"))


# ── The four escape vectors ───────────────────────────────────────────

ESCAPES = [
    pytest.param("../outside/secret.txt", id="parent-traversal"),
    pytest.param("a/b/../../../outside/secret.txt", id="nested-traversal"),
    pytest.param("/etc/passwd", id="absolute-key"),
    pytest.param("..", id="bare-parent"),
]


@pytest.mark.parametrize("key", ESCAPES)
class TestEscapesAreRejected:
    async def test_download_rejects(self, adapter, key):
        with pytest.raises(StoragePathError):
            await adapter.download(key)

    async def test_upload_rejects(self, adapter, key):
        with pytest.raises(StoragePathError):
            await adapter.upload(key, b"x", "text/plain")

    async def test_delete_rejects(self, adapter, key):
        with pytest.raises(StoragePathError):
            await adapter.delete(key)

    def test_get_url_rejects(self, adapter, key):
        with pytest.raises(StoragePathError):
            adapter.get_url(key)

    def test_get_url_still_rejects_traversal_before_reporting_unavailable(self, adapter, key):
        """Ordering guard: _resolve() must run before get_url raises
        StoragePublicUrlUnavailableError, so a traversal key still surfaces
        the containment error, not "public URLs are unavailable", which
        would leak that the check for the *escape* never ran at all."""
        with pytest.raises(StoragePathError) as exc:
            adapter.get_url(key)
        assert not isinstance(exc.value, StoragePublicUrlUnavailableError)

    async def test_list_keys_rejects(self, adapter, key):
        with pytest.raises(StoragePathError):
            await adapter.list_keys(key)


async def test_upload_escape_writes_nothing(adapter, root):
    """The rejection must happen before any filesystem write."""
    with pytest.raises(StoragePathError):
        await adapter.upload("../outside/planted.txt", b"x", "text/plain")

    assert not (root / "outside" / "planted.txt").exists()


async def test_absolute_key_does_not_read_through(adapter, root):
    """Reading an absolute path must raise rather than return contents."""
    with pytest.raises(StoragePathError):
        await adapter.download(str(root / "outside" / "secret.txt"))


async def test_rejecting_a_key_is_not_logged_at_the_adapter_layer(adapter, glados_caplog):
    """_resolve() does not log before raising StoragePathError:
    domain_error_handler already logs it unconditionally (it's in
    exception_handlers._LOG_ERROR), and that line's message already names
    the offending key, so a second line here would only double it."""
    with pytest.raises(StoragePathError):
        await adapter.download("../outside/secret.txt")

    assert glados_caplog.records == []


# ── Legitimate keys still work ────────────────────────────────────────


class TestLegitimateKeysStillWork:
    async def test_round_trip(self, adapter):
        await adapter.upload("users/avatars/1.png", b"payload", "image/png")

        data, _ = await adapter.download("users/avatars/1.png")

        assert data == b"payload"

    async def test_nested_key_with_harmless_dots(self, adapter):
        """A filename containing dots is fine, only `..` *segments* are
        traversal."""
        await adapter.upload("files/my..file..txt", b"payload", "text/plain")

        assert (await adapter.download("files/my..file..txt"))[0] == b"payload"

    async def test_traversal_that_stays_inside_is_allowed(self, adapter):
        """`a/../b` never leaves the root, so there is nothing to reject,
        the check is about the destination, not the spelling."""
        await adapter.upload("a/../b.txt", b"payload", "text/plain")

        assert (await adapter.download("b.txt"))[0] == b"payload"

    async def test_list_keys_returns_paths_relative_to_the_root(self, adapter):
        await adapter.upload("backups/files/2026-01-01/x.txt", b"payload", "text/plain")

        keys = await adapter.list_keys("backups/files/")

        assert keys == ["backups/files/2026-01-01/x.txt"]

    async def test_delete_is_still_a_noop_for_a_missing_key(self, adapter):
        await adapter.delete("nothing/here.txt")

    def test_get_url_reports_public_urls_unavailable(self, adapter):
        """Local storage has no unauthenticated `/media` mount to build a
        URL against, so get_url raises for every
        legitimate key rather than returning one."""
        with pytest.raises(StoragePublicUrlUnavailableError):
            adapter.get_url("users/avatars/1.png")

    async def test_list_keys_on_a_missing_prefix_is_empty(self, adapter):
        assert await adapter.list_keys("does/not/exist") == []

    async def test_empty_prefix_lists_everything(self, adapter):
        await adapter.upload("one.txt", b"1", "text/plain")
        await adapter.upload("nested/two.txt", b"2", "text/plain")

        assert sorted(await adapter.list_keys()) == ["nested/two.txt", "one.txt"]
