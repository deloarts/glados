"""
Unit tests for the branding/company-logo "remove this asset" use cases and
the login video's read side. None of these five had any
test reference at all (only their Upload* counterparts are covered, by
tests/unit/test_admin_settings_upload_use_cases.py).

  - DeleteBrandingFavicon
  - DeleteBrandingLogo
  - DeleteLoginBackgroundVideo
  - DeleteCompanyLogo
  - GetLoginBackgroundVideo

No database, no HTTP. Repository fake is the shared FakeAdminSettingsRepository
(tests/unit/admin_settings/fakes.py); storage is a small in-memory fake local
to this file, since none of the shared fakes implement IStoragePort.
"""

import pytest

from src.modules.platform.application.use_cases.admin_settings.delete_branding_favicon import (
    DeleteBrandingFavicon,
)
from src.modules.platform.application.use_cases.admin_settings.delete_branding_logo import (
    DeleteBrandingLogo,
)
from src.modules.platform.application.use_cases.admin_settings.delete_company_logo import (
    DeleteCompanyLogo,
)
from src.modules.platform.application.use_cases.admin_settings.delete_login_background_video import (
    DeleteLoginBackgroundVideo,
)
from src.modules.platform.application.use_cases.admin_settings.get_login_background_video import (
    GetLoginBackgroundVideo,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import LoginVideoNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_actor(permissions: list[str] | None = None) -> User:
    return make_user(username="admin", full_name="Admin User", permissions=permissions)


class FakeStorage:
    """Minimal IStoragePort stand-in: records every delete() call, and can
    be told to raise so the best-effort delete path is provable."""

    def __init__(self, *, raise_on_delete: bool = False) -> None:
        self.deleted: list[str] = []
        self._raise = raise_on_delete

    async def delete(self, key: str) -> None:
        if self._raise:
            raise RuntimeError("storage backend unreachable")
        self.deleted.append(key)

    async def upload(self, key, data, content_type) -> None:
        raise NotImplementedError

    async def download(self, key):
        raise NotImplementedError

    async def list_keys(self, prefix: str = ""):
        raise NotImplementedError

    def get_url(self, key: str) -> str:
        raise NotImplementedError

    async def test_connection(self) -> None:
        raise NotImplementedError


# ── DeleteBrandingFavicon ────────────────────────────────────────────


class TestDeleteBrandingFavicon:
    async def test_requires_write_settings(self):
        repo = FakeAdminSettingsRepository()
        use_case = DeleteBrandingFavicon(repo, FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_actor(permissions=[]))

    async def test_clears_the_key_and_deletes_from_storage(self):
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        use_case = DeleteBrandingFavicon(repo, storage, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert result.has_favicon is False
        assert repo.branding.favicon_key is None
        assert storage.deleted == ["original-favicon-key"]
        # Untouched siblings.
        assert repo.branding.logo_key == "original-logo-key"
        assert repo.branding.login_background_video_key == "original-video-key"
        assert len(repo.audit_log) == 1
        assert repo.audit_log[0].settings_domain == "branding"

    async def test_no_favicon_configured_skips_storage_call(self):
        repo = FakeAdminSettingsRepository()
        repo.branding.favicon_key = None
        storage = FakeStorage()
        use_case = DeleteBrandingFavicon(repo, storage, uow=FakeUnitOfWork())

        await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert storage.deleted == []

    async def test_storage_none_is_tolerated(self):
        """Storage disabled entirely (get_optional_storage_adapter returns
        None): the key still clears, no AttributeError on a None storage."""
        repo = FakeAdminSettingsRepository()
        use_case = DeleteBrandingFavicon(repo, storage=None, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert result.has_favicon is False

    async def test_storage_delete_failure_is_logged_not_raised(self, glados_caplog):
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage(raise_on_delete=True)
        use_case = DeleteBrandingFavicon(repo, storage, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert result.has_favicon is False  # the DB change still applies
        assert any("Failed to delete storage object" in r.message for r in glados_caplog.records)


# ── DeleteBrandingLogo ───────────────────────────────────────────────


class TestDeleteBrandingLogo:
    async def test_requires_write_settings(self):
        repo = FakeAdminSettingsRepository()
        use_case = DeleteBrandingLogo(repo, FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_actor(permissions=[]))

    async def test_clears_the_key_and_deletes_from_storage(self):
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        use_case = DeleteBrandingLogo(repo, storage, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert result.has_logo is False
        assert repo.branding.logo_key is None
        assert storage.deleted == ["original-logo-key"]
        assert repo.branding.favicon_key == "original-favicon-key"


# ── DeleteLoginBackgroundVideo ───────────────────────────────────────


class TestDeleteLoginBackgroundVideo:
    async def test_requires_write_settings(self):
        repo = FakeAdminSettingsRepository()
        use_case = DeleteLoginBackgroundVideo(repo, FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_actor(permissions=[]))

    async def test_clears_the_key_and_deletes_from_storage(self):
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        use_case = DeleteLoginBackgroundVideo(repo, storage, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert result.has_login_background_video is False
        assert repo.branding.login_background_video_key is None
        assert storage.deleted == ["original-video-key"]
        assert repo.branding.logo_key == "original-logo-key"
        assert repo.branding.favicon_key == "original-favicon-key"


# ── DeleteCompanyLogo ────────────────────────────────────────────────


class TestDeleteCompanyLogo:
    async def test_requires_write_settings(self):
        repo = FakeAdminSettingsRepository()
        use_case = DeleteCompanyLogo(repo, FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_actor(permissions=[]))

    async def test_clears_the_key_and_deletes_from_storage(self):
        repo = FakeAdminSettingsRepository()
        repo.general.company_logo_key = "original-company-logo-key"
        storage = FakeStorage()
        use_case = DeleteCompanyLogo(repo, storage, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert result.has_company_logo is False
        assert repo.general.company_logo_key is None
        assert storage.deleted == ["original-company-logo-key"]

    async def test_no_logo_configured_skips_storage_call(self):
        repo = FakeAdminSettingsRepository()
        assert repo.general.company_logo_key is None
        storage = FakeStorage()
        use_case = DeleteCompanyLogo(repo, storage, uow=FakeUnitOfWork())

        await use_case.execute(actor=make_actor([Permission.WRITE_SETTINGS]))

        assert storage.deleted == []


# ── GetLoginBackgroundVideo ──────────────────────────────────────────


class TestGetLoginBackgroundVideo:
    async def test_no_video_configured_raises_not_found(self):
        repo = FakeAdminSettingsRepository()
        repo.branding.login_background_video_key = None
        use_case = GetLoginBackgroundVideo(repo, FakeStorage())

        with pytest.raises(LoginVideoNotFoundError):
            await use_case.execute()

    async def test_storage_disabled_raises_not_found_even_with_a_configured_key(self):
        repo = FakeAdminSettingsRepository()
        assert repo.branding.login_background_video_key == "original-video-key"
        use_case = GetLoginBackgroundVideo(repo, storage=None)

        with pytest.raises(LoginVideoNotFoundError):
            await use_case.execute()

    async def test_streams_the_configured_video(self):
        class DownloadingStorage(FakeStorage):
            async def download(self, key: str) -> tuple[bytes, str]:
                assert key == "original-video-key"
                return b"video-bytes", "video/mp4"

        repo = FakeAdminSettingsRepository()
        use_case = GetLoginBackgroundVideo(repo, DownloadingStorage())

        data, content_type = await use_case.execute()

        assert data == b"video-bytes"
        assert content_type == "video/mp4"

    def test_unauthenticated_no_actor_argument_required(self):
        """The login screen has no session yet, so execute() takes no actor
        and performs no permission check, unlike every Delete* use case
        above."""
        import inspect

        assert list(inspect.signature(GetLoginBackgroundVideo.execute).parameters) == ["self"]
