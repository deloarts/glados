"""Startup guard for production signing, encryption and backup keys, for
the initial admin and database passwords, and for the S3 secret of the
bundled SeaweedFS.

Pure helper so the check is unit-testable without running the lifespan
(the integration suite deliberately skips the lifespan entirely).
"""

from urllib.parse import urlsplit

from src.modules.platform.infrastructure.config.settings import InitSettings
from src.modules.platform.infrastructure.config.settings import SecuritySettings

# Values shipped by .env.example / dev docs. A production process must
# never run with any of these, or with two keys set to the same value.
_INSECURE_PLACEHOLDERS = frozenset(
    {
        "dev-insecure-change-me-in-production",
        "change_me",
    }
)

# The shortest key a production process accepts, in characters. The signing
# keys are HMAC-SHA256 keys, which RFC 7518 wants at least 256 bits long, and
# the encryption and backup keys are stretched by HKDF-SHA256 into 256-bit
# keys, which cannot be stronger than their input. `openssl rand -hex 32`
# gives 64 characters and comfortably passes.
MIN_KEY_LENGTH = 32

# The shortest initial admin password a production process accepts. The
# system account it belongs to holds every permission and is reset to this
# value on every start; the stack env script generates 24 characters.
MIN_INIT_PASSWORD_LENGTH = 12

# The shortest S3 secret of the bundled SeaweedFS a production process
# accepts. nginx serves the storage's S3 API under /objects/ on the public
# hostname, so anyone who knows the secret can list and read every stored
# file; the stack env script generates 32 characters.
MIN_SEAWEEDFS_SECRET_LENGTH = 24


def _assert_long_enough(env_name: str, value: str) -> None:
    if len(value) < MIN_KEY_LENGTH:
        raise RuntimeError(
            f"{env_name} is {len(value)} characters long; production needs at least"
            f" {MIN_KEY_LENGTH}. Generate one with `openssl rand -hex 32`."
        )


def assert_production_secrets_ok(security: SecuritySettings, *, debug: bool) -> None:
    """Refuse to boot a non-debug process with missing, placeholder, short or
    reused keys.

    Debug mode keeps the existing dev-ergonomics carve-out: no checks.
    Raises RuntimeError with a message naming the offending key so an
    operator knows which one to rotate.
    """
    if debug:
        return
    if security.secret_key_persistent in _INSECURE_PLACEHOLDERS:
        raise RuntimeError(
            "SECURITY__SECRET_KEY_PERSISTENT must be set to a strong secret in production."
        )
    if security.secret_key_non_persistent in _INSECURE_PLACEHOLDERS:
        raise RuntimeError(
            "SECURITY__SECRET_KEY_NON_PERSISTENT must be set to a strong secret in production."
        )
    _assert_long_enough("SECURITY__SECRET_KEY_PERSISTENT", security.secret_key_persistent)
    _assert_long_enough("SECURITY__SECRET_KEY_NON_PERSISTENT", security.secret_key_non_persistent)
    if security.secret_key_persistent == security.secret_key_non_persistent:
        raise RuntimeError(
            "SECURITY__SECRET_KEY_PERSISTENT and SECURITY__SECRET_KEY_NON_PERSISTENT must"
            " differ: equal keys defeat the persistent/non-persistent token isolation."
        )
    if not security.encryption_key or security.encryption_key in _INSECURE_PLACEHOLDERS:
        raise RuntimeError("SECURITY__ENCRYPTION_KEY must be set to a strong secret in production.")
    _assert_long_enough("SECURITY__ENCRYPTION_KEY", security.encryption_key)
    if security.encryption_key in (
        security.secret_key_persistent,
        security.secret_key_non_persistent,
    ):
        raise RuntimeError(
            "SECURITY__ENCRYPTION_KEY must differ from both signing keys: rotating a signing"
            " key would otherwise make every stored secret unreadable."
        )
    _assert_backup_key_ok(security)


def _assert_backup_key_ok(security: SecuritySettings) -> None:
    """The backup key is optional, since a deployment may leave backups off,
    and without it the backup job refuses to run instead. Once set, it must
    be a real secret of its own: an archive encrypted with the key of the
    secrets inside it, or with a signing key, would travel with that key."""
    backup_key = security.backup_encryption_key
    if backup_key is None:
        return
    if not backup_key or backup_key in _INSECURE_PLACEHOLDERS:
        raise RuntimeError(
            "SECURITY__BACKUP_ENCRYPTION_KEY must be a strong secret in production, or unset."
        )
    _assert_long_enough("SECURITY__BACKUP_ENCRYPTION_KEY", backup_key)
    if backup_key in (
        security.encryption_key,
        security.secret_key_persistent,
        security.secret_key_non_persistent,
    ):
        raise RuntimeError(
            "SECURITY__BACKUP_ENCRYPTION_KEY must differ from SECURITY__ENCRYPTION_KEY and"
            " both signing keys, so a backup never carries the key that opens it."
        )


def assert_production_credentials_ok(init: InitSettings, database_url: str, *, debug: bool) -> None:
    """Refuse to boot a non-debug process whose initial admin password is a
    placeholder or short, or whose database password is a placeholder.

    The values in .env.example are public, so a deployment copied from it
    would otherwise run its system account, which holds every permission,
    with a password anyone can read in the repository."""
    if debug:
        return
    if init.password in _INSECURE_PLACEHOLDERS or len(init.password) < MIN_INIT_PASSWORD_LENGTH:
        raise RuntimeError(
            f"INIT__PASSWORD must be a strong password of at least {MIN_INIT_PASSWORD_LENGTH}"
            " characters in production, not the sample value."
        )
    if (urlsplit(database_url).password or "") in _INSECURE_PLACEHOLDERS:
        raise RuntimeError(
            "The password in DATABASE__URL is the sample value; set a strong one for both"
            " DATABASE__URL and POSTGRES_PASSWORD."
        )


def assert_bundled_storage_secret_ok(
    secret_key: str, compose_profiles: str, *, debug: bool
) -> None:
    """Refuse to boot a non-debug process next to a bundled SeaweedFS whose S3
    secret is empty, the sample value or short.

    The check applies when COMPOSE_PROFILES names `seaweedfs`, or when a
    secret is set at all. Without a secret SeaweedFS runs its S3 API without
    authentication, and nginx forwards /objects/ to it on the public
    hostname, so an empty or public secret opens every stored file to
    anyone. The stack's own `seaweedfs-check` service refuses the same
    values when the profile is started from the command line."""
    if debug:
        return
    profiles = {name.strip() for name in compose_profiles.split(",")}
    if "seaweedfs" not in profiles and not secret_key:
        return
    if secret_key in _INSECURE_PLACEHOLDERS or len(secret_key) < MIN_SEAWEEDFS_SECRET_LENGTH:
        raise RuntimeError(
            "SEAWEEDFS_SECRET_KEY must be a strong secret of at least"
            f" {MIN_SEAWEEDFS_SECRET_LENGTH} characters when the bundled SeaweedFS runs,"
            " not empty and not the sample value. Generate one with `openssl rand -hex 32`"
            " and enter the same pair in Admin Settings, Storage."
        )
