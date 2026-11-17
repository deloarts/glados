"""Boot-time guard for keys and passwords (src/modules/platform/infrastructure/config/boot_guard.py)."""

import pytest

from src.modules.platform.infrastructure.config.boot_guard import MIN_INIT_PASSWORD_LENGTH
from src.modules.platform.infrastructure.config.boot_guard import MIN_KEY_LENGTH
from src.modules.platform.infrastructure.config.boot_guard import MIN_SEAWEEDFS_SECRET_LENGTH
from src.modules.platform.infrastructure.config.boot_guard import assert_bundled_storage_secret_ok
from src.modules.platform.infrastructure.config.boot_guard import assert_production_credentials_ok
from src.modules.platform.infrastructure.config.boot_guard import assert_production_secrets_ok
from src.modules.platform.infrastructure.config.settings import InitSettings
from src.modules.platform.infrastructure.config.settings import SecuritySettings


def _security(
    persistent: str,
    non_persistent: str,
    encryption: str | None = "a-strong-encryption-key-of-enough-length",
) -> SecuritySettings:
    return SecuritySettings(
        secret_key_persistent=persistent,
        secret_key_non_persistent=non_persistent,
        encryption_key=encryption,
    )


def test_placeholder_persistent_key_is_rejected_in_prod() -> None:
    security = _security(
        "dev-insecure-change-me-in-production", "a-strong-and-unique-key-of-enough-length"
    )
    with pytest.raises(RuntimeError, match="SECURITY__SECRET_KEY_PERSISTENT"):
        assert_production_secrets_ok(security, debug=False)


def test_placeholder_non_persistent_key_is_rejected_in_prod() -> None:
    security = _security("a-strong-and-unique-key-of-enough-length", "change_me")
    with pytest.raises(RuntimeError, match="SECURITY__SECRET_KEY_NON_PERSISTENT"):
        assert_production_secrets_ok(security, debug=False)


def test_identical_keys_are_rejected_in_prod() -> None:
    security = _security(
        "same-strong-key-of-enough-length-here", "same-strong-key-of-enough-length-here"
    )
    with pytest.raises(RuntimeError, match="must differ"):
        assert_production_secrets_ok(security, debug=False)


def test_two_distinct_strong_keys_pass() -> None:
    security = _security(
        "first-strong-key-of-enough-length-here", "second-strong-key-of-enough-length-here"
    )
    assert_production_secrets_ok(security, debug=False)


def test_debug_mode_skips_the_guard() -> None:
    security = _security("change_me", "change_me")
    assert_production_secrets_ok(security, debug=True)


@pytest.mark.parametrize("encryption", [None, "", "change_me"])
def test_missing_or_placeholder_encryption_key_is_rejected_in_prod(encryption) -> None:
    security = _security(
        "first-strong-key-of-enough-length-here",
        "second-strong-key-of-enough-length-here",
        encryption,
    )
    with pytest.raises(RuntimeError, match="SECURITY__ENCRYPTION_KEY"):
        assert_production_secrets_ok(security, debug=False)


def test_encryption_key_reusing_a_signing_key_is_rejected_in_prod() -> None:
    security = _security(
        "first-strong-key-of-enough-length-here",
        "second-strong-key-of-enough-length-here",
        "first-strong-key-of-enough-length-here",
    )
    with pytest.raises(RuntimeError, match="must differ from both signing keys"):
        assert_production_secrets_ok(security, debug=False)


def _with_backup_key(backup_key: str | None) -> SecuritySettings:
    security = _security(
        "first-strong-key-of-enough-length-here", "second-strong-key-of-enough-length-here"
    )
    security.backup_encryption_key = backup_key
    return security


def test_an_unset_backup_key_passes() -> None:
    """Optional at boot: without it the backup job refuses to run instead."""
    assert_production_secrets_ok(_with_backup_key(None), debug=False)


def test_a_distinct_backup_key_passes() -> None:
    assert_production_secrets_ok(
        _with_backup_key("a-strong-backup-key-of-enough-length-here"), debug=False
    )


@pytest.mark.parametrize("backup_key", ["", "change_me"])
def test_an_empty_or_placeholder_backup_key_is_rejected_in_prod(backup_key) -> None:
    with pytest.raises(RuntimeError, match="SECURITY__BACKUP_ENCRYPTION_KEY"):
        assert_production_secrets_ok(_with_backup_key(backup_key), debug=False)


@pytest.mark.parametrize(
    "backup_key",
    [
        "first-strong-key-of-enough-length-here",
        "second-strong-key-of-enough-length-here",
        "a-strong-encryption-key-of-enough-length",
    ],
)
def test_a_backup_key_reusing_another_key_is_rejected_in_prod(backup_key) -> None:
    with pytest.raises(RuntimeError, match="must differ"):
        assert_production_secrets_ok(_with_backup_key(backup_key), debug=False)


@pytest.mark.parametrize(
    ("field", "env_name"),
    [
        ("secret_key_persistent", "SECURITY__SECRET_KEY_PERSISTENT"),
        ("secret_key_non_persistent", "SECURITY__SECRET_KEY_NON_PERSISTENT"),
        ("encryption_key", "SECURITY__ENCRYPTION_KEY"),
        ("backup_encryption_key", "SECURITY__BACKUP_ENCRYPTION_KEY"),
    ],
)
def test_a_key_shorter_than_the_minimum_is_rejected_in_prod(field: str, env_name: str) -> None:
    security = _with_backup_key("a-strong-backup-key-of-enough-length-here")
    setattr(security, field, "x" * (MIN_KEY_LENGTH - 1))
    with pytest.raises(RuntimeError, match=f"{env_name} is {MIN_KEY_LENGTH - 1} characters long"):
        assert_production_secrets_ok(security, debug=False)


def test_a_key_of_exactly_the_minimum_length_passes() -> None:
    security = _security("p" * MIN_KEY_LENGTH, "n" * MIN_KEY_LENGTH, "e" * MIN_KEY_LENGTH)
    security.backup_encryption_key = "b" * MIN_KEY_LENGTH
    assert_production_secrets_ok(security, debug=False)


def test_debug_mode_accepts_short_keys() -> None:
    assert_production_secrets_ok(_security("short", "other", "tiny"), debug=True)


# ── Initial admin and database passwords ─────────────────────────────────

_STRONG_URL = "postgresql+psycopg://glados:s3cret-and-long-enough@postgres:5432/glados"


def _init(password: str) -> InitSettings:
    return InitSettings(full_name="Admin", mail="admin@example.com", password=password)


def test_the_sample_initial_password_is_rejected_in_prod() -> None:
    with pytest.raises(RuntimeError, match="INIT__PASSWORD"):
        assert_production_credentials_ok(_init("change_me"), _STRONG_URL, debug=False)


def test_a_short_initial_password_is_rejected_in_prod() -> None:
    short = "x" * (MIN_INIT_PASSWORD_LENGTH - 1)
    with pytest.raises(RuntimeError, match="INIT__PASSWORD"):
        assert_production_credentials_ok(_init(short), _STRONG_URL, debug=False)


def test_the_sample_database_password_is_rejected_in_prod() -> None:
    url = "postgresql+psycopg://glados:change_me@postgres:5432/glados"
    with pytest.raises(RuntimeError, match="DATABASE__URL"):
        assert_production_credentials_ok(_init("a-long-initial-password"), url, debug=False)


def test_strong_credentials_pass_in_prod() -> None:
    # Returns None and raises nothing when both passwords are acceptable.
    assert (
        assert_production_credentials_ok(_init("a-long-initial-password"), _STRONG_URL, debug=False)
        is None
    )


def test_debug_skips_the_credential_checks() -> None:
    url = "postgresql+psycopg://glados:change_me@postgres:5432/glados"
    assert assert_production_credentials_ok(_init("change_me"), url, debug=True) is None


_STRONG_SEAWEEDFS_SECRET = "s" * MIN_SEAWEEDFS_SECRET_LENGTH


@pytest.mark.parametrize("secret", ["", "change_me", "s" * (MIN_SEAWEEDFS_SECRET_LENGTH - 1)])
def test_a_weak_seaweedfs_secret_is_rejected_when_the_profile_runs(secret: str) -> None:
    with pytest.raises(RuntimeError, match="SEAWEEDFS_SECRET_KEY"):
        assert_bundled_storage_secret_ok(secret, "cloudflare, seaweedfs", debug=False)


@pytest.mark.parametrize("secret", ["change_me", "short"])
def test_a_weak_seaweedfs_secret_is_rejected_even_without_the_profile_named(secret: str) -> None:
    """A stack started with `--profile seaweedfs` on the command line leaves
    COMPOSE_PROFILES empty, so a set secret is checked on its own."""
    with pytest.raises(RuntimeError, match="SEAWEEDFS_SECRET_KEY"):
        assert_bundled_storage_secret_ok(secret, "", debug=False)


def test_no_seaweedfs_and_no_secret_passes() -> None:
    assert_bundled_storage_secret_ok("", "cloudflare,autoupdate", debug=False)


def test_a_strong_seaweedfs_secret_passes() -> None:
    assert_bundled_storage_secret_ok(_STRONG_SEAWEEDFS_SECRET, "seaweedfs", debug=False)


def test_debug_skips_the_seaweedfs_check() -> None:
    assert_bundled_storage_secret_ok("", "seaweedfs", debug=True)
