"""
Proves that the user account writes persist what they report. Creating a
user, uploading and removing an avatar, confirming a voluntary TOTP enrolment
and the startup seeding of the system user are each read back from a fresh database session, so a use
case that forgets to commit its unit of work fails here instead of
silently losing the write.
"""

from typing import Any

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_mail_service
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from tests.factories import TEST_PASSWORD

WEB = "/api/v1/web"


async def _column(username: str, column: Any) -> Any:
    async with SessionLocal() as fresh:
        return await fresh.scalar(select(column).where(UserOrmModel.username == username))


class _SilentMailService:
    """Stands in for SMTP: the welcome mail is irrelevant to persistence."""

    async def send_welcome(self, **_: Any) -> None:
        return None


async def test_created_user_is_persisted(auth_client) -> None:
    admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

    app.dependency_overrides[get_mail_service] = _SilentMailService
    try:
        response = await admin.post(
            f"{WEB}/users/",
            json={
                "username": "newcomer",
                "full_name": "New Comer",
                "email": "newcomer@example.com",
                "password": "a-long-password",
            },
        )
    finally:
        app.dependency_overrides.pop(get_mail_service, None)

    assert response.status_code == 201, response.text
    assert await _column("newcomer", UserOrmModel.email) == "newcomer@example.com"


async def test_avatar_upload_is_persisted(db, auth_client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(tmp_path))
    await db.execute(text("DELETE FROM admin_storage_settings"))
    await SqlAlchemyAdminSettingsRepository(db).save_storage(
        AdminStorageSettings(
            id=1,
            provider="local",
            enabled=True,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key=None,
            region=None,
            use_ssl=False,
            backup_enabled=False,
            backup_path="backups",
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    client = await auth_client(username="portrait", email="portrait@example.com")

    response = await client.post(
        f"{WEB}/users/me/avatar",
        files={"file": ("me.png", b"\x89PNG\r\n\x1a\nrest-of-the-file", "image/png")},
    )

    assert response.status_code == 200, response.text
    key = await _column("portrait", UserOrmModel.avatar_key)
    assert key is not None
    assert (tmp_path / key).exists()


async def test_avatar_removal_is_persisted(db, auth_client) -> None:
    client = await auth_client(username="pictured", email="pictured@example.com")
    await db.execute(
        update(UserOrmModel)
        .where(UserOrmModel.username == "pictured")
        .values(avatar_key="users/avatars/1/old.png")
    )
    await db.commit()

    response = await client.delete(f"{WEB}/users/me/avatar")

    assert response.status_code == 200, response.text
    assert await _column("pictured", UserOrmModel.avatar_key) is None


async def test_voluntary_totp_confirmation_is_persisted(auth_client, seeded_security) -> None:
    client = await auth_client(username="careful", email="careful@example.com")
    enrolled = await client.post(f"{WEB}/users/me/totp/enroll", json={"password": TEST_PASSWORD})
    assert enrolled.status_code == 200, enrolled.text

    code = pyotp.TOTP(enrolled.json()["secret"]).now()
    confirmed = await client.post(f"{WEB}/users/me/totp/confirm", json={"totp_code": code})

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["access_token"] is None
    assert await _column("careful", UserOrmModel.totp_enabled) is True


async def test_enrolling_again_with_2fa_on_keeps_the_active_secret(
    auth_client, seeded_security
) -> None:
    client = await auth_client(username="guarded", email="guarded@example.com")
    enrolled = await client.post(f"{WEB}/users/me/totp/enroll", json={"password": TEST_PASSWORD})
    code = pyotp.TOTP(enrolled.json()["secret"]).now()
    await client.post(f"{WEB}/users/me/totp/confirm", json={"totp_code": code})
    active = await _column("guarded", UserOrmModel.totp_secret)

    again = await client.post(f"{WEB}/users/me/totp/enroll")

    assert again.status_code == 409, again.text
    assert again.json()["code"] == "TOTPAlreadyEnabledError"
    assert await _column("guarded", UserOrmModel.totp_secret) == active


async def test_system_user_seeding_is_persisted(db, create_user) -> None:
    init = InitDatabase(
        user_repo=SqlAlchemyUserRepository(db),
        admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
        print_template_repo=SqlAlchemyPrintTemplateRepository(db),
        db=db,
    )

    await init._ensure_system_user()
    assert await _column(SYSTEM_USER, UserOrmModel.full_name) == cfg.init.full_name

    await db.execute(
        update(UserOrmModel).where(UserOrmModel.username == SYSTEM_USER).values(full_name="Drift")
    )
    await db.commit()
    await init._ensure_system_user()
    assert await _column(SYSTEM_USER, UserOrmModel.full_name) == cfg.init.full_name


async def test_a_second_system_user_is_refused_by_the_database(db, create_user) -> None:
    """The partial unique index on is_systemuser lets at most one row carry
    the flag, since it grants every permission, and leaves unflagged rows
    alone."""
    await create_user(username=SYSTEM_USER, email="system@example.com", is_systemuser=True)
    await create_user(username="first", email="first@example.com")
    await create_user(username="second", email="second@example.com")

    with pytest.raises(IntegrityError, match="is_systemuser"):
        await create_user(username="stray", email="stray@example.com", is_systemuser=True)
    await db.rollback()

    async with SessionLocal() as fresh:
        flagged = await fresh.scalars(
            select(UserOrmModel.username).where(UserOrmModel.is_systemuser.is_(True))
        )
        assert flagged.all() == [SYSTEM_USER]
