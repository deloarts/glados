"""
Boot step that keeps the time tracking user fingerprints valid after an
encryption key rotation. The fingerprint is keyed with a key derived from
SECURITY__ENCRYPTION_KEY, so a new key changes every fingerprint; rows whose
stored key id differs from the current one are recomputed from their user
name. It runs right after reencrypt_stored_secrets, when user names written
under the previous key are readable again. A row whose user name cannot be
decrypted keeps its old fingerprint and is skipped; its owner has to enter
the credentials again anyway. Idempotent and cheap once done.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.operations.adapters.outbound.persistence.models.user_time_tracking_credentials_model import (
    UserTimeTrackingCredentialsOrmModel,
)
from src.modules.operations.domain.services.time_tracking_rules import fingerprint_subject
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint,
)
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint_key_id,
)
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.secret_box import encryption_configured


async def recompute_time_tracking_fingerprints(db: AsyncSession) -> int:
    """Returns the number of fingerprints rewritten."""
    if not encryption_configured():
        return 0
    key_id = time_tracking_fingerprint_key_id()
    model = UserTimeTrackingCredentialsOrmModel
    rows = (
        await db.scalars(select(model).where(model.time_tracking_user_fingerprint_key_id != key_id))
    ).all()
    rewritten = 0
    for row in rows:
        if not row.time_tracking_user:
            log.warning(
                "Time tracking credentials of user ID=%s cannot be decrypted, "
                "their fingerprint was not recomputed.",
                row.user_id,
            )
            continue
        row.time_tracking_user_fingerprint = time_tracking_fingerprint(
            fingerprint_subject(row.time_tracking_user)
        )
        row.time_tracking_user_fingerprint_key_id = key_id
        rewritten += 1
    if rewritten:
        await db.commit()
        log.info(f"Recomputed {rewritten} time tracking user fingerprint(s) for the current key.")
    return rewritten
