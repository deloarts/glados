"""
Unit tests for the four admin-settings image/video upload use cases
(branding logo, company logo, branding favicon, login background video).
No database, no HTTP, no storage backend, all dependencies are in-memory
fakes local to this file (tests/unit/admin_settings/fakes.py's shared fake
repository covers the CRUD update use cases, not these).

Each use case checks the uploaded bytes' magic number against its
declared content type, on top of the header-only allow-list check. This
file's "signature mismatch" tests pin that down: a payload that is not
what its content type claims must be rejected with the same
*InvalidTypeError the header check uses, not a new exception type.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.application.use_cases.admin_settings.upload_branding_favicon import (
    UploadBrandingFavicon,
)
from src.modules.platform.application.use_cases.admin_settings.upload_branding_logo import (
    UploadBrandingLogo,
)
from src.modules.platform.application.use_cases.admin_settings.upload_company_logo import (
    UploadCompanyLogo,
)
from src.modules.platform.application.use_cases.admin_settings.upload_login_background_video import (
    UploadLoginBackgroundVideo,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import BrandingImageInvalidTypeError
from src.modules.platform.domain.exceptions import BrandingImageTooLargeError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import LoginVideoInvalidTypeError
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit.fakes import FakeUnitOfWork

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"rest-of-the-file"
JPEG_BYTES = b"\xff\xd8\xff" + b"rest-of-the-file"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"rest-of-the-file"
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"rest-of-the-file"

# ── Helpers ───────────────────────────────────────────────────────────


def make_actor(permissions: list[str] | None = None, is_systemuser: bool = False) -> User:
    return User(
        id=1,
        username="admin",
        full_name="Admin User",
        email="admin@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=is_systemuser,
        permissions=permissions if permissions is not None else [],
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


def make_branding(**overrides: object) -> AdminBrandingSettings:
    defaults: dict[str, object] = dict(
        id=1,
        app_name="Glados",
        app_description=None,
        footer_text=None,
        logo_url=None,
        favicon_url=None,
        logo_key=None,
        favicon_key=None,
        login_background_video_key=None,
    )
    defaults.update(overrides)
    return AdminBrandingSettings(**defaults)  # type: ignore[arg-type]


def make_general(**overrides: object) -> AdminGeneralSettings:
    defaults: dict[str, object] = dict(
        id=1,
        company_name=None,
        company_legal_name=None,
        company_logo_key=None,
        contact_email=None,
        imprint_url=None,
        privacy_url=None,
        support_url=None,
        product_number_pattern="",
        project_number_pattern="",
        allow_headless_projects=True,
        empty_value_placeholder="-",
        office_launcher_enabled=False,
        office_sharepoint_url="",
        currency="EUR",
        default_language=Language.enGB,
        default_timezone="Europe/Vienna",
        default_date_format=DateFormat.ISO,
    )
    defaults.update(overrides)
    return AdminGeneralSettings(**defaults)  # type: ignore[arg-type]


class FakeAdminSettingsRepository:
    """Only the methods the four upload use cases actually call."""

    def __init__(
        self,
        branding: AdminBrandingSettings | None = None,
        general: AdminGeneralSettings | None = None,
    ) -> None:
        self.branding = branding or make_branding()
        self.general = general or make_general()
        self.audit_entries: list[AdminSettingsAuditEntry] = []

    async def get_branding(self) -> AdminBrandingSettings:
        return self.branding

    async def save_branding(self, settings: AdminBrandingSettings) -> AdminBrandingSettings:
        self.branding = settings
        return settings

    async def get_general(self) -> AdminGeneralSettings:
        return self.general

    async def save_general(self, settings: AdminGeneralSettings) -> AdminGeneralSettings:
        self.general = settings
        return settings

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry:
        self.audit_entries.append(entry)
        return entry


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes, str]] = []
        self.deleted: list[str] = []

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.uploaded.append((key, data, content_type))

    async def delete(self, key: str) -> None:
        self.deleted.append(key)

    async def download(self, key: str) -> tuple[bytes, str]:
        raise NotImplementedError

    async def list_keys(self, prefix: str = "") -> list[str]:
        return []

    def get_url(self, key: str) -> str:
        return f"http://x/media/{key}"

    async def test_connection(self) -> None:
        return None


# ── UploadBrandingLogo ───────────────────────────────────────────────


class TestUploadBrandingLogo:
    async def test_accepts_a_genuine_png(self) -> None:
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        uc = UploadBrandingLogo(repo=repo, storage=storage, uow=FakeUnitOfWork())

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=PNG_BYTES, content_type="image/png"
        )

        assert storage.uploaded[0][0] == "public/logo.png"
        assert repo.branding.logo_key == "public/logo.png"

    async def test_rejects_content_whose_signature_does_not_match_its_declared_type(self) -> None:
        repo = FakeAdminSettingsRepository()
        uc = UploadBrandingLogo(repo=repo, storage=FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(BrandingImageInvalidTypeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=JPEG_BYTES,
                content_type="image/png",
            )

    async def test_requires_write_settings(self) -> None:
        uc = UploadBrandingLogo(
            repo=FakeAdminSettingsRepository(), storage=FakeStorage(), uow=FakeUnitOfWork()
        )

        with pytest.raises(InsufficientPermissionsError):
            await uc.execute(actor=make_actor([]), data=PNG_BYTES, content_type="image/png")

    async def test_without_storage_raises_storage_not_enabled(self) -> None:
        uc = UploadBrandingLogo(
            repo=FakeAdminSettingsRepository(), storage=None, uow=FakeUnitOfWork()
        )

        with pytest.raises(StorageNotEnabledError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=PNG_BYTES,
                content_type="image/png",
            )

    async def test_oversize_payload_is_rejected(self) -> None:
        uc = UploadBrandingLogo(
            repo=FakeAdminSettingsRepository(), storage=FakeStorage(), uow=FakeUnitOfWork()
        )

        with pytest.raises(BrandingImageTooLargeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=b"\x89PNG\r\n\x1a\n" + b"x" * (6 * 1024 * 1024),
                content_type="image/png",
            )


# ── UploadCompanyLogo ────────────────────────────────────────────────


class TestUploadCompanyLogo:
    async def test_accepts_a_genuine_png(self) -> None:
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        uc = UploadCompanyLogo(repo=repo, storage=storage, uow=FakeUnitOfWork())

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=PNG_BYTES, content_type="image/png"
        )

        assert repo.general.company_logo_key == "public/company-logo.png"

    async def test_rejects_content_whose_signature_does_not_match_its_declared_type(self) -> None:
        repo = FakeAdminSettingsRepository()
        uc = UploadCompanyLogo(repo=repo, storage=FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(BrandingImageInvalidTypeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=JPEG_BYTES,
                content_type="image/png",
            )

    async def test_replacing_deletes_the_previous_key(self) -> None:
        repo = FakeAdminSettingsRepository(general=make_general(company_logo_key="public/old.png"))
        storage = FakeStorage()
        uc = UploadCompanyLogo(repo=repo, storage=storage, uow=FakeUnitOfWork())

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=PNG_BYTES, content_type="image/png"
        )

        assert "public/old.png" in storage.deleted


# ── UploadBrandingFavicon ────────────────────────────────────────────


class TestUploadBrandingFavicon:
    async def test_accepts_a_genuine_ico(self) -> None:
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        uc = UploadBrandingFavicon(repo=repo, storage=storage, uow=FakeUnitOfWork())
        ico_bytes = b"\x00\x00\x01\x00" + b"rest-of-the-file"

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]),
            data=ico_bytes,
            content_type="image/x-icon",
        )

        assert repo.branding.favicon_key == "public/favicon.ico"

    async def test_rejects_content_whose_signature_does_not_match_its_declared_type(self) -> None:
        repo = FakeAdminSettingsRepository()
        uc = UploadBrandingFavicon(repo=repo, storage=FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(BrandingImageInvalidTypeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=JPEG_BYTES,
                content_type="image/x-icon",
            )


# ── UploadLoginBackgroundVideo ───────────────────────────────────────


class TestUploadLoginBackgroundVideo:
    @pytest.mark.parametrize(
        ("content_type", "data", "expected_ext"),
        [
            ("video/mp4", MP4_BYTES, ".mp4"),
            ("video/webm", WEBM_BYTES, ".webm"),
        ],
    )
    async def test_accepts_a_genuine_video(
        self, content_type: str, data: bytes, expected_ext: str
    ) -> None:
        repo = FakeAdminSettingsRepository()
        storage = FakeStorage()
        uc = UploadLoginBackgroundVideo(repo=repo, storage=storage, uow=FakeUnitOfWork())

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=data, content_type=content_type
        )

        assert repo.branding.login_background_video_key == f"public/login-background{expected_ext}"

    async def test_rejects_a_png_declared_as_mp4(self) -> None:
        """The header-only check would have let this through, since
        image content is never in the video allow-list to begin with,
        but a client could still declare video/mp4 while sending
        arbitrary bytes, which is exactly what the signature check is
        for."""
        repo = FakeAdminSettingsRepository()
        uc = UploadLoginBackgroundVideo(repo=repo, storage=FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(LoginVideoInvalidTypeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=PNG_BYTES,
                content_type="video/mp4",
            )

    async def test_rejects_a_webm_declared_as_mp4(self) -> None:
        repo = FakeAdminSettingsRepository()
        uc = UploadLoginBackgroundVideo(repo=repo, storage=FakeStorage(), uow=FakeUnitOfWork())

        with pytest.raises(LoginVideoInvalidTypeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=WEBM_BYTES,
                content_type="video/mp4",
            )

    async def test_replacing_deletes_the_previous_key(self) -> None:
        repo = FakeAdminSettingsRepository(
            branding=make_branding(login_background_video_key="public/old.mp4")
        )
        storage = FakeStorage()
        uc = UploadLoginBackgroundVideo(repo=repo, storage=storage, uow=FakeUnitOfWork())

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=MP4_BYTES, content_type="video/mp4"
        )

        assert "public/old.mp4" in storage.deleted


# ── Transaction and storage ordering (all four) ──────────────────────


class SequencedAdminSettingsRepository(FakeAdminSettingsRepository):
    """Writes its saves into a log shared with the storage and unit of work
    fakes, so a test can assert the order across all three."""

    def __init__(
        self, log: list[str], fail_save: bool = False, log_audit: bool = False, **kwargs: object
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._log = log
        self._fail_save = fail_save
        self._log_audit = log_audit

    def _record_save(self) -> None:
        if self._fail_save:
            self._log.append("save:failed")
            raise RuntimeError("database unavailable")
        self._log.append("save")

    async def save_branding(self, settings: AdminBrandingSettings) -> AdminBrandingSettings:
        self._record_save()
        return await super().save_branding(settings)

    async def save_general(self, settings: AdminGeneralSettings) -> AdminGeneralSettings:
        self._record_save()
        return await super().save_general(settings)

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry:
        if self._log_audit:
            self._log.append("audit")
        return await super().append_audit(entry)


class SequencedStorage(FakeStorage):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._log.append(f"upload:{key}")
        await super().upload(key, data, content_type)

    async def delete(self, key: str) -> None:
        self._log.append(f"delete:{key}")
        await super().delete(key)


class RecordingUow:
    """Logs its commits; with `fail_commit_number` set, that commit (counted
    from 1) raises instead, standing in for a database that drops out."""

    def __init__(self, log: list[str], fail_commit_number: int | None = None) -> None:
        self._log = log
        self._fail_commit_number = fail_commit_number
        self._commits = 0

    async def commit(self) -> None:
        self._commits += 1
        if self._commits == self._fail_commit_number:
            self._log.append("commit:failed")
            raise RuntimeError("database unavailable")
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


_ORDERING_CASES = [
    pytest.param(
        UploadBrandingLogo,
        PNG_BYTES,
        "image/png",
        {"branding": make_branding(logo_key="public/logo.svg")},
        "public/logo.svg",
        "public/logo.png",
        id="branding-logo",
    ),
    pytest.param(
        UploadCompanyLogo,
        PNG_BYTES,
        "image/png",
        {"general": make_general(company_logo_key="public/company-logo.svg")},
        "public/company-logo.svg",
        "public/company-logo.png",
        id="company-logo",
    ),
    pytest.param(
        UploadBrandingFavicon,
        PNG_BYTES,
        "image/png",
        {"branding": make_branding(favicon_key="public/favicon.ico")},
        "public/favicon.ico",
        "public/favicon.png",
        id="favicon",
    ),
    pytest.param(
        UploadLoginBackgroundVideo,
        MP4_BYTES,
        "video/mp4",
        {"branding": make_branding(login_background_video_key="public/login-background.webm")},
        "public/login-background.webm",
        "public/login-background.mp4",
        id="login-video",
    ),
]


@pytest.mark.parametrize(
    ("uc_cls", "data", "content_type", "repo_kwargs", "old_key", "new_key"), _ORDERING_CASES
)
class TestUploadOrdering:
    async def test_commits_then_uploads_then_saves_then_deletes_the_old_object(
        self,
        uc_cls: type,
        data: bytes,
        content_type: str,
        repo_kwargs: dict[str, object],
        old_key: str,
        new_key: str,
    ) -> None:
        log: list[str] = []
        uc = uc_cls(
            repo=SequencedAdminSettingsRepository(log, log_audit=True, **repo_kwargs),
            storage=SequencedStorage(log),
            uow=RecordingUow(log),
        )

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=data, content_type=content_type
        )

        # The read transaction ends before the upload, the new key and its
        # audit entry commit together, and the old object goes only after
        # that commit.
        assert log == [
            "commit",
            f"upload:{new_key}",
            "save",
            "audit",
            "commit",
            f"delete:{old_key}",
        ]

    async def test_failed_commit_deletes_the_new_object_and_keeps_the_old_one(
        self,
        uc_cls: type,
        data: bytes,
        content_type: str,
        repo_kwargs: dict[str, object],
        old_key: str,
        new_key: str,
    ) -> None:
        log: list[str] = []
        uc = uc_cls(
            repo=SequencedAdminSettingsRepository(log, log_audit=True, **repo_kwargs),
            storage=SequencedStorage(log),
            uow=RecordingUow(log, fail_commit_number=2),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]), data=data, content_type=content_type
            )

        assert log == [
            "commit",
            f"upload:{new_key}",
            "save",
            "audit",
            "commit:failed",
            f"delete:{new_key}",
        ]

    async def test_failed_save_deletes_the_new_object_and_keeps_the_old_one(
        self,
        uc_cls: type,
        data: bytes,
        content_type: str,
        repo_kwargs: dict[str, object],
        old_key: str,
        new_key: str,
    ) -> None:
        log: list[str] = []
        uc = uc_cls(
            repo=SequencedAdminSettingsRepository(log, fail_save=True, **repo_kwargs),
            storage=SequencedStorage(log),
            uow=FakeUnitOfWork(),
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]), data=data, content_type=content_type
            )

        assert log == [f"upload:{new_key}", "save:failed", f"delete:{new_key}"]


class TestSameKeyReplacement:
    async def test_same_type_replacement_never_deletes_the_overwritten_key(self) -> None:
        log: list[str] = []
        repo = SequencedAdminSettingsRepository(
            log, branding=make_branding(logo_key="public/logo.png")
        )
        uc = UploadBrandingLogo(repo=repo, storage=SequencedStorage(log), uow=FakeUnitOfWork())

        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]), data=PNG_BYTES, content_type="image/png"
        )

        assert log == ["upload:public/logo.png", "save"]

    async def test_failed_save_of_a_same_type_replacement_keeps_the_stored_key(self) -> None:
        log: list[str] = []
        repo = SequencedAdminSettingsRepository(
            log, fail_save=True, branding=make_branding(logo_key="public/logo.png")
        )
        uc = UploadBrandingLogo(repo=repo, storage=SequencedStorage(log), uow=FakeUnitOfWork())

        with pytest.raises(RuntimeError):
            await uc.execute(
                actor=make_actor([Permission.WRITE_SETTINGS]),
                data=PNG_BYTES,
                content_type="image/png",
            )

        assert log == ["upload:public/logo.png", "save:failed"]
