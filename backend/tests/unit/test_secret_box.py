"""Encryption of stored secrets (src/modules/platform/infrastructure/security/secret_box.py)
and the EncryptedString column type built on it."""

import pytest

import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.encrypted_type import _encrypted_columns
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.secret_box import ENCRYPTED_PREFIX
from src.modules.platform.infrastructure.security.secret_box import EncryptionKeyMissingError
from src.modules.platform.infrastructure.security.secret_box import SecretDecryptionError
from src.modules.platform.infrastructure.security.secret_box import decrypt_secret
from src.modules.platform.infrastructure.security.secret_box import encrypt_secret
from src.modules.platform.infrastructure.security.secret_box import needs_reencryption


@pytest.fixture
def keys(monkeypatch: pytest.MonkeyPatch):
    def _set(current: str | None, previous: str | None = None) -> None:
        monkeypatch.setattr(cfg.security, "encryption_key", current)
        monkeypatch.setattr(cfg.security, "encryption_key_previous", previous)

    _set("unit-key-a")
    return _set


def test_roundtrip_is_prefixed_and_not_plaintext(keys) -> None:
    stored = encrypt_secret("smtp-pass")
    assert stored.startswith(ENCRYPTED_PREFIX)
    assert "smtp-pass" not in stored
    assert decrypt_secret(stored) == "smtp-pass"


def test_same_plaintext_encrypts_differently_each_time(keys) -> None:
    assert encrypt_secret("smtp-pass") != encrypt_secret("smtp-pass")


def test_wrong_key_fails_to_decrypt(keys) -> None:
    stored = encrypt_secret("smtp-pass")
    keys("unit-key-b")
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(stored)


def test_previous_key_still_decrypts_and_flags_reencryption(keys) -> None:
    stored = encrypt_secret("smtp-pass")
    assert not needs_reencryption(stored)
    keys("unit-key-b", previous="unit-key-a")
    assert decrypt_secret(stored) == "smtp-pass"
    assert needs_reencryption(stored)
    assert not needs_reencryption(encrypt_secret("smtp-pass"))


def test_unencrypted_value_needs_no_reencryption(keys) -> None:
    assert not needs_reencryption("not-encrypted")


def test_missing_key_refuses_to_encrypt(keys) -> None:
    keys(None)
    with pytest.raises(EncryptionKeyMissingError):
        encrypt_secret("smtp-pass")


class TestEncryptedString:
    def test_bind_encrypts_and_result_decrypts(self, keys) -> None:
        column_type = EncryptedString()
        stored = column_type.process_bind_param("smtp-pass", None)  # type: ignore[arg-type]
        assert stored is not None and stored.startswith(ENCRYPTED_PREFIX)
        assert column_type.process_result_value(stored, None) == "smtp-pass"  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_values_pass_through(self, keys, value) -> None:
        column_type = EncryptedString()
        assert column_type.process_bind_param(value, None) == value  # type: ignore[arg-type]
        assert column_type.process_result_value(value, None) == value  # type: ignore[arg-type]

    def test_already_encrypted_value_is_not_encrypted_twice(self, keys) -> None:
        stored = encrypt_secret("smtp-pass")
        assert EncryptedString().process_bind_param(stored, None) == stored  # type: ignore[arg-type]

    def test_unencrypted_value_reads_as_none_and_logs(self, keys, glados_caplog) -> None:
        assert EncryptedString().process_result_value("not-encrypted", None) is None  # type: ignore[arg-type]
        assert any("is not encrypted" in r.getMessage() for r in glados_caplog.records)

    def test_undecryptable_value_reads_as_none_and_logs(self, keys, glados_caplog) -> None:
        stored = encrypt_secret("smtp-pass")
        keys("unit-key-b")
        assert EncryptedString().process_result_value(stored, None) is None  # type: ignore[arg-type]
        assert any("could not be decrypted" in r.getMessage() for r in glados_caplog.records)


def test_every_stored_secret_column_is_encrypted() -> None:
    assert {f"{table.name}.{column.name}" for table, column in _encrypted_columns()} == {
        "admin_mail_settings.password",
        "admin_storage_settings.access_key",
        "admin_storage_settings.secret_key",
        "admin_pdm_settings.password",
        "admin_pdm_settings.session_token",
        "user_table.totp_secret",
        "webhook_subscription_table.secret",
        "user_time_tracking_credentials.time_tracking_user",
        "admin_time_tracking_settings.api_key",
        "admin_edp_settings.pat",
        "admin_stock_settings.api_key",
    }
