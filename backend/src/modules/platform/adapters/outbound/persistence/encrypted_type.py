"""
Column type that stores a string encrypted at rest with
src/modules/platform/infrastructure/security/secret_box.py. Encryption happens when the value
is bound to a statement and decryption when a row is loaded, so entities,
repositories and use cases keep handling plaintext and need no changes.

A value that no configured key decrypts (the key was changed without
keeping the old one as SECURITY__ENCRYPTION_KEY_PREVIOUS), and a value
without the encrypted prefix, which this type never writes, load as None
and log an error: the setting then reads as unconfigured and an admin
re-enters it, rather than the app failing every request that touches the
row. reencrypt_stored_secrets moves values written under the previous key
onto the current one on every boot.
"""

from typing import Any

from sqlalchemy import Dialect
from sqlalchemy import String
from sqlalchemy import select
from sqlalchemy import type_coerce
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import TypeDecorator

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.secret_box import SecretDecryptionError
from src.modules.platform.infrastructure.security.secret_box import decrypt_secret
from src.modules.platform.infrastructure.security.secret_box import encrypt_secret
from src.modules.platform.infrastructure.security.secret_box import encryption_configured
from src.modules.platform.infrastructure.security.secret_box import is_encrypted
from src.modules.platform.infrastructure.security.secret_box import needs_reencryption


class EncryptedString(TypeDecorator[str]):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if not value or is_encrypted(value):
            return value
        return encrypt_secret(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if not value:
            return value
        if not is_encrypted(value):
            log.error("A stored secret is not encrypted, treating it as unset.")
            return None
        try:
            return decrypt_secret(value)
        except SecretDecryptionError:
            log.error(
                "A stored secret could not be decrypted with SECURITY__ENCRYPTION_KEY"
                " or SECURITY__ENCRYPTION_KEY_PREVIOUS, treating it as unset."
            )
            return None


def _encrypted_columns() -> list[tuple[Any, Any]]:
    return [
        (table, column)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, EncryptedString)
    ]


async def reencrypt_stored_secrets(db: AsyncSession) -> int:
    """Move values encrypted with the previous key onto the current one,
    for every EncryptedString column. Idempotent
    and cheap once done, so it runs on every boot. Skipped while no key is
    configured, which only a debug process is allowed to boot without.

    Reads bypass the column type through type_coerce so the stored value is
    seen as is; the write goes through it and is encrypted with the current
    key. Returns the number of values rewritten."""
    if not encryption_configured():
        log.warning("SECURITY__ENCRYPTION_KEY is not set, stored secrets stay as they are.")
        return 0
    rewritten = 0
    for table, column in _encrypted_columns():
        rows = (
            await db.execute(
                select(table.c.id, type_coerce(column, String)).where(
                    column.is_not(None), type_coerce(column, String) != ""
                )
            )
        ).all()
        for row_id, stored in rows:
            if not needs_reencryption(stored):
                continue
            plain = decrypt_secret(stored)
            await db.execute(update(table).where(table.c.id == row_id).values({column.name: plain}))
            rewritten += 1
    if rewritten:
        await db.commit()
        log.info(f"Encrypted {rewritten} stored secret(s) with the current encryption key.")
    return rewritten
