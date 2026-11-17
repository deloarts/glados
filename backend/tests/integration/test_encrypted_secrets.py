"""Secrets in EncryptedString columns are stored encrypted and read back in
plaintext, values under a rotated-out key are re-encrypted by
reencrypt_stored_secrets (run on every boot by InitDatabase), and a stored
value without the encrypted prefix reads as unset. The mail password covers
the singleton settings rows, the TOTP secret and the webhook secret cover
multi-row tables."""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.encrypted_type import (
    reencrypt_stored_secrets,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.secret_box import ENCRYPTED_PREFIX
from src.modules.platform.infrastructure.security.secret_box import encrypt_secret


@pytest.fixture(autouse=True)
async def _seed_mail(db) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_mail(
        AdminMailSettings(
            id=1,
            enabled=True,
            host="smtp.example.com",
            port=587,
            user="glados@example.com",
            password=None,
            from_address=None,
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=20,
            send_lock_minutes=60,
            alert_recipients=[],
        )
    )
    await db.commit()


async def _raw_password(db) -> str | None:
    result = await db.execute(text("SELECT password FROM admin_mail_settings WHERE id = 1"))
    return result.scalar()


async def _set_raw_password(db, value: str) -> None:
    await db.execute(
        text("UPDATE admin_mail_settings SET password = :p WHERE id = 1"), {"p": value}
    )
    await db.commit()


async def _save_password(db, password: str) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    mail = await repo.get_mail()
    mail.password = password
    await repo.save_mail(mail)
    await db.commit()


async def test_saved_password_is_encrypted_at_rest_and_read_back_in_plaintext(db) -> None:
    await _save_password(db, "smtp-pass")

    raw = await _raw_password(db)
    assert raw is not None and raw.startswith(ENCRYPTED_PREFIX)
    assert "smtp-pass" not in raw
    db.expunge_all()
    assert (await SqlAlchemyAdminSettingsRepository(db).get_mail()).password == "smtp-pass"


async def test_unencrypted_value_reads_as_unset_and_is_left_alone_on_boot(db) -> None:
    await _set_raw_password(db, "not-encrypted")
    db.expunge_all()
    assert (await SqlAlchemyAdminSettingsRepository(db).get_mail()).password is None

    assert await reencrypt_stored_secrets(db) == 0
    assert await _raw_password(db) == "not-encrypted"


async def test_boot_moves_values_from_the_previous_key_to_the_current_one(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_raw_password(db, encrypt_secret("rotated-pass"))
    old_key = cfg.security.encryption_key
    monkeypatch.setattr(cfg.security, "encryption_key", "integration-new-key")
    monkeypatch.setattr(cfg.security, "encryption_key_previous", old_key)

    assert await reencrypt_stored_secrets(db) == 1
    monkeypatch.setattr(cfg.security, "encryption_key_previous", None)
    db.expunge_all()
    assert (await SqlAlchemyAdminSettingsRepository(db).get_mail()).password == "rotated-pass"


async def _raw(db, sql: str, **params) -> str | None:
    return (await db.execute(text(sql), params)).scalar()


async def test_totp_secret_is_encrypted_at_rest(db, create_user) -> None:
    repo = SqlAlchemyUserRepository(db)
    user = await create_user()
    user.totp_secret = "JBSWY3DPEHPK3PXP"
    await repo.save(user)

    raw = await _raw(db, "SELECT totp_secret FROM user_table WHERE id = :id", id=user.id)
    assert raw.startswith(ENCRYPTED_PREFIX)
    db.expunge_all()
    assert (await repo.get_by_id(user.id)).totp_secret == "JBSWY3DPEHPK3PXP"


async def test_webhook_secret_is_encrypted_at_rest(db, create_user) -> None:
    creator = await create_user()
    repo = SqlAlchemyWebhookSubscriptionRepository(db)
    saved = await repo.save(
        WebhookSubscription(
            id=0,
            name="erp",
            url="https://erp.example.com/hook",
            secret="whsec-plain",
            event_types=["*"],
            is_active=True,
            created=datetime.now(UTC),
            creator_id=creator.id,
        )
    )

    raw = await _raw(
        db, "SELECT secret FROM webhook_subscription_table WHERE id = :id", id=saved.id
    )
    assert raw.startswith(ENCRYPTED_PREFIX)
    db.expunge_all()
    assert (await repo.get_by_id(saved.id)).secret == "whsec-plain"
