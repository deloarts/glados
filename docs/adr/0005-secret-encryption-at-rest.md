# 0005 encrypt readable secrets at rest with a dedicated key

- Status: accepted
- Date: 2026-10-05

## context

Some secrets must be read back in plaintext because Glados uses them to log in elsewhere: the SMTP password, object storage keys, the PDM password and cached session token, webhook signing secrets and users' TOTP secrets. They cannot be hashed like user passwords. Stored in plaintext they leak through every database dump, backup and SQL injection read. Deriving the encryption key from a signing key would tie two unrelated rotations together, since rotating a signing key is how everyone gets logged out.

## decision

These columns use an `EncryptedString` SQLAlchemy type that encrypts on write and decrypts on read, so entities, repositories and use cases stay unchanged. The key comes from `SECURITY__ENCRYPTION_KEY`, separate from the signing keys; HKDF-SHA256 derives a Fernet key from it, and stored values carry an `enc:v1:` prefix. `SECURITY__ENCRYPTION_KEY_PREVIOUS` keeps the old key readable during a rotation, and startup re-encrypts every value under the current key. Production refuses to boot without a key, with a placeholder, or with a key equal to a signing key.

## consequences

A database dump alone no longer reveals the secrets; a compromised host still does, since the key sits next to the app. A value no configured key can decrypt loads as unset and logs an error, so losing the key means re-entering credentials, recreating webhook subscriptions and resetting two-factor enrolment. The key therefore has to be backed up together with the database, as described in [OPERATIONS.md](../OPERATIONS.md) and [INSTALLATION.md](../INSTALLATION.md).
