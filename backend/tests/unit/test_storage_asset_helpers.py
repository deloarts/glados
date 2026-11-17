"""
Coverage for src/modules/platform/application/services/storage_asset.py, the shared
upload/delete helpers used by every stored-asset use case
(branding images, login video, user avatars, bought-item/order files).

The two "best effort" helpers are the interesting ones: they deliberately
swallow storage failures rather than failing the request, so a change
that let an exception escape would break uploads in production while
every use-case test, which fakes storage, still passed.
"""

import pytest

from src.modules.platform.application.services.storage_asset import assert_allowed_type
from src.modules.platform.application.services.storage_asset import assert_magic_bytes_match
from src.modules.platform.application.services.storage_asset import assert_within_size_limit
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.application.services.storage_asset import resolve_extension
from src.modules.platform.domain.exceptions import StoragePublicUrlUnavailableError

# ── Fakes ─────────────────────────────────────────────────────────────


class _FakeStorage:
    """Minimal IStoragePort stand-in, only delete/get_url are used here."""

    def __init__(self, raises: Exception | None = None, url: str | None = None):
        self._raises = raises
        self._url = url
        self.deleted: list[str] = []
        self.url_lookups: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        if self._raises:
            raise self._raises

    def get_url(self, path: str, file_name: str | None = None) -> str | None:
        self.url_lookups.append(path)
        if self._raises:
            raise self._raises
        return self._url


class _CustomError(Exception):
    pass


# ── assert_within_size_limit ──────────────────────────────────────────


class TestAssertWithinSizeLimit:
    def test_under_the_limit_passes(self):
        assert_within_size_limit(b"x" * 10, 1024, error=_CustomError, label="Avatar")

    def test_exactly_at_the_limit_passes(self):
        assert_within_size_limit(b"x" * 1024, 1024, error=_CustomError, label="Avatar")

    def test_over_the_limit_raises_the_supplied_error_type(self):
        with pytest.raises(_CustomError):
            assert_within_size_limit(b"x" * 1025, 1024, error=_CustomError, label="Avatar")

    def test_message_reports_the_limit_in_mb_and_the_actual_byte_count(self):
        with pytest.raises(_CustomError) as exc:
            assert_within_size_limit(
                b"x" * (3 * 1024 * 1024), 2 * 1024 * 1024, error=_CustomError, label="Avatar"
            )
        assert "Avatar" in str(exc.value)
        assert "2 MB" in str(exc.value)
        assert str(3 * 1024 * 1024) in str(exc.value)

    def test_empty_payload_always_passes(self):
        assert_within_size_limit(b"", 0, error=_CustomError, label="Avatar")


# ── assert_allowed_type ───────────────────────────────────────────────


class TestAssertAllowedType:
    def test_allowed_type_in_a_set_passes(self):
        assert_allowed_type(
            "image/png", {"image/png", "image/jpeg"}, error=_CustomError, label="image"
        )

    def test_allowed_type_in_a_dict_passes(self):
        """Callers pass either a set or a content-type -> extension dict;
        membership is checked against the dict's keys."""
        assert_allowed_type("image/png", {"image/png": ".png"}, error=_CustomError, label="image")

    def test_disallowed_type_raises(self):
        with pytest.raises(_CustomError):
            assert_allowed_type("application/pdf", {"image/png"}, error=_CustomError, label="image")

    def test_message_lists_the_allowed_types_sorted(self):
        with pytest.raises(_CustomError) as exc:
            assert_allowed_type(
                "application/pdf",
                {"image/png", "image/jpeg"},
                error=_CustomError,
                label="image",
            )
        assert "application/pdf" in str(exc.value)
        assert "image/jpeg, image/png" in str(exc.value)


# ── assert_magic_bytes_match ────────────────────────────────────────────

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"rest-of-the-file"
_JPEG_BYTES = b"\xff\xd8\xff" + b"rest-of-the-file"
_GIF_BYTES = b"GIF89a" + b"rest-of-the-file"
_WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"rest-of-the-file"
_ICO_BYTES = b"\x00\x00\x01\x00" + b"rest-of-the-file"
_SVG_BYTES = b"<?xml version='1.0'?>\n<svg xmlns='http://www.w3.org/2000/svg'></svg>"
_MP4_BYTES = b"\x00\x00\x00\x18" + b"ftyp" + b"mp42rest-of-the-file"
_WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"rest-of-the-file"
_UNRELATED_BYTES = b"MZ\x90\x00this-is-not-any-of-the-above"


class TestAssertMagicBytesMatch:
    @pytest.mark.parametrize(
        ("content_type", "data"),
        [
            ("image/png", _PNG_BYTES),
            ("image/jpeg", _JPEG_BYTES),
            ("image/gif", _GIF_BYTES),
            ("image/webp", _WEBP_BYTES),
            ("image/x-icon", _ICO_BYTES),
            ("image/vnd.microsoft.icon", _ICO_BYTES),
            ("image/svg+xml", _SVG_BYTES),
            ("video/mp4", _MP4_BYTES),
            ("video/webm", _WEBM_BYTES),
        ],
    )
    def test_matching_signature_passes(self, content_type, data):
        assert_magic_bytes_match(data, content_type, error=_CustomError, label="file")

    @pytest.mark.parametrize(
        "content_type",
        [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "image/x-icon",
            "image/vnd.microsoft.icon",
            "image/svg+xml",
            "video/mp4",
            "video/webm",
        ],
    )
    def test_mismatched_signature_raises_the_supplied_error_type(self, content_type):
        with pytest.raises(_CustomError):
            assert_magic_bytes_match(
                _UNRELATED_BYTES, content_type, error=_CustomError, label="file"
            )

    def test_error_message_reports_the_label_and_declared_type(self):
        with pytest.raises(_CustomError) as exc:
            assert_magic_bytes_match(
                _UNRELATED_BYTES, "image/png", error=_CustomError, label="Logo"
            )
        assert "Logo" in str(exc.value)
        assert "image/png" in str(exc.value)

    def test_cross_type_payload_is_rejected(self):
        """A JPEG payload declared as image/png must not pass just because
        both are registered image types."""
        with pytest.raises(_CustomError):
            assert_magic_bytes_match(_JPEG_BYTES, "image/png", error=_CustomError, label="file")

    def test_truncated_payload_is_rejected_rather_than_raising_indexerror(self):
        with pytest.raises(_CustomError):
            assert_magic_bytes_match(b"\x89P", "image/png", error=_CustomError, label="file")

    def test_unregistered_content_type_passes_through_unchecked(self):
        """A content type with no signature check (none of the five upload
        use cases currently allow one) is not this function's concern;
        assert_allowed_type is what would have already rejected it."""
        assert_magic_bytes_match(
            b"anything at all", "application/pdf", error=_CustomError, label="file"
        )


# ── resolve_extension ─────────────────────────────────────────────────


class TestResolveExtension:
    def test_override_wins_over_the_mimetypes_guess(self):
        assert resolve_extension("image/jpeg", {"image/jpeg": ".jpg"}) == ".jpg"

    def test_falls_back_to_the_mimetypes_guess_without_an_override(self):
        assert resolve_extension("image/png") == ".png"

    def test_falls_back_to_the_guess_when_overrides_lack_this_type(self):
        assert resolve_extension("image/png", {"image/jpeg": ".jpg"}) == ".png"

    def test_unknown_content_type_falls_back_to_bin(self):
        assert resolve_extension("application/x-totally-made-up") == ".bin"

    def test_empty_overrides_dict_is_treated_as_no_overrides(self):
        assert resolve_extension("image/png", {}) == ".png"


# ── delete_storage_object_best_effort ─────────────────────────────────


class TestDeleteStorageObjectBestEffort:
    async def test_delegates_to_the_storage_port(self):
        storage = _FakeStorage()
        await delete_storage_object_best_effort(storage, "some/key", context="avatar")  # type: ignore[arg-type]
        assert storage.deleted == ["some/key"]

    async def test_swallows_storage_failures(self):
        storage = _FakeStorage(raises=RuntimeError("S3 is down"))
        await delete_storage_object_best_effort(storage, "some/key", context="avatar")  # type: ignore[arg-type]
        assert storage.deleted == ["some/key"]


# ── get_storage_url_best_effort ───────────────────────────────────────


class TestGetStorageUrlBestEffort:
    def test_returns_the_url_from_the_storage_port(self):
        storage = _FakeStorage(url="https://cdn.example.com/x.png")
        result = get_storage_url_best_effort(storage, "x.png", context="avatar")  # type: ignore[arg-type]
        assert result == "https://cdn.example.com/x.png"
        assert storage.url_lookups == ["x.png"]

    def test_returns_none_on_storage_failure_instead_of_raising(self):
        storage = _FakeStorage(raises=RuntimeError("S3 is down"))
        assert get_storage_url_best_effort(storage, "x.png", context="avatar") is None  # type: ignore[arg-type]

    def test_logs_a_warning_on_a_generic_storage_failure(self, glados_caplog):
        """The broad except still warns: a caught exception from S3/Azure
        means the backend is actually unreachable, unlike the expected,
        permanent StoragePublicUrlUnavailableError below."""
        storage = _FakeStorage(raises=RuntimeError("S3 is down"))
        get_storage_url_best_effort(storage, "x.png", context="avatar")  # type: ignore[arg-type]

        assert any(r.levelname == "WARNING" for r in glados_caplog.records)

    def test_passes_through_a_none_url_from_the_port(self):
        storage = _FakeStorage(url=None)
        assert get_storage_url_best_effort(storage, "x.png", context="avatar") is None  # type: ignore[arg-type]

    def test_public_url_unavailable_returns_none_without_logging_a_warning(self, glados_caplog):
        """Local storage's get_url raises
        StoragePublicUrlUnavailableError for every key: that is the
        expected, permanent outcome, not a failure worth a WARNING on every
        file in every request (unlike the generic-exception path above)."""
        storage = _FakeStorage(raises=StoragePublicUrlUnavailableError("no public URL"))

        result = get_storage_url_best_effort(storage, "x.png", context="avatar")  # type: ignore[arg-type]

        assert result is None
        assert glados_caplog.records == []
