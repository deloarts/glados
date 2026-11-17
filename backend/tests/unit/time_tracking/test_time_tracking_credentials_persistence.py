"""
The credentials repository against an in-memory SQLite database: the user
name is stored as an `enc:v1:` value and read back in plaintext, the sealed
value is stored as it comes, a user name no key decrypts reads as None (the
re-entry state), the auth-failed mark and clearing the sealed value leave
the other values alone, the holders list, and a fingerprint collision is
reported without naming the other user. Also the fingerprint itself: its
normalisation, its key being separate from the at-rest key, and the boot
step that recomputes fingerprints after a key rotation.
"""

import hashlib
import hmac
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.modules.operations.adapters.outbound.persistence.repositories.time_tracking_credentials_repository import (
    SqlAlchemyUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.adapters.outbound.persistence.time_tracking_fingerprints import (
    recompute_time_tracking_fingerprints,
)
from src.modules.operations.domain.errors import TimeTrackingUserAlreadyLinkedError
from src.modules.operations.domain.services.time_tracking_rules import CredentialsInvalidReason
from src.modules.operations.domain.services.time_tracking_rules import credentials_invalid_reason
from src.modules.operations.domain.services.time_tracking_rules import fingerprint_subject
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import _derive
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint,
)
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint_key_id,
)
from src.modules.platform.adapters.outbound.persistence.encrypted_type import (
    reencrypt_stored_secrets,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.secret_box import ENCRYPTED_PREFIX
from src.modules.platform.infrastructure.security.secret_box import _fernet_for
from tests.unit.time_tracking._helpers import KEY_ID
from tests.unit.time_tracking._helpers import NOW
from tests.unit.time_tracking._helpers import SEALED
from tests.unit.time_tracking._helpers import make_credentials


@pytest.fixture
def keys(monkeypatch: pytest.MonkeyPatch):
    def _set(current: str | None, previous: str | None = None) -> None:
        monkeypatch.setattr(cfg.security, "encryption_key", current)
        monkeypatch.setattr(cfg.security, "encryption_key_previous", previous)

    _set("unit-key-a")
    return _set


@pytest.fixture
async def db(keys) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sessions() as session:
        for user_id in (7, 8):
            session.add(
                UserOrmModel(
                    id=user_id,
                    username=f"user{user_id}",
                    full_name="Test User",
                    email=f"user{user_id}@example.test",
                    created=NOW,
                    hashed_password="x",
                    is_active=True,
                    is_systemuser=False,
                    permissions=[],
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


def fingerprinted(user_id: int = 7, user: str = "jane.doe", **overrides: object):
    return make_credentials(
        user_id=user_id,
        id=0,
        time_tracking_user=user,
        time_tracking_user_fingerprint=time_tracking_fingerprint(fingerprint_subject(user)),
        time_tracking_user_fingerprint_key_id=time_tracking_fingerprint_key_id(),
        **overrides,
    )


async def raw(db: AsyncSession, column: str, user_id: int = 7) -> str:
    result = await db.execute(
        text(f"SELECT {column} FROM user_time_tracking_credentials WHERE user_id = :u"),
        {"u": user_id},
    )
    return str(result.scalar())


async def test_the_user_name_is_encrypted_and_the_sealed_value_stored_as_is(
    db: AsyncSession,
) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await db.commit()

    stored_user = await raw(db, "time_tracking_user")
    assert stored_user.startswith(ENCRYPTED_PREFIX)
    assert "jane.doe" not in stored_user
    assert await raw(db, "time_tracking_sealed_credentials") == SEALED
    db.expunge_all()
    loaded = await repo.get_by_user(7)
    assert loaded is not None
    assert loaded.time_tracking_user == "jane.doe"
    assert loaded.time_tracking_sealed_credentials == SEALED
    assert loaded.time_tracking_credential_key_id == KEY_ID
    assert loaded.time_tracking_auth_failed_at is None
    assert loaded.time_tracking_consent_at.tzinfo is not None


async def test_saving_again_replaces_the_row(db: AsyncSession) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    first = await repo.save(fingerprinted())
    second = await repo.save(replace(fingerprinted(), time_tracking_binding="new-binding"))
    await db.commit()

    assert second.id == first.id
    assert await repo.get_count() == 1
    assert (await repo.get_by_user(7)).time_tracking_binding == "new-binding"  # type: ignore[union-attr]


async def test_undecryptable_values_read_as_the_re_entry_state(db: AsyncSession, keys) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await db.commit()
    db.expunge_all()

    keys("unit-key-without-the-old-one")
    loaded = await repo.get_by_user(7)

    assert loaded is not None
    assert loaded.time_tracking_user is None
    assert (
        credentials_invalid_reason(loaded, current_key_id=KEY_ID)
        is CredentialsInvalidReason.UNDECRYPTABLE
    )


async def test_auth_failed_mark_leaves_the_stored_values_alone(db: AsyncSession, keys) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await db.commit()
    before = await raw(db, "time_tracking_user")

    await repo.mark_auth_failed(7, NOW)
    await db.commit()

    assert await raw(db, "time_tracking_user") == before
    assert await raw(db, "time_tracking_sealed_credentials") == SEALED
    db.expunge_all()
    assert (await repo.get_by_user(7)).time_tracking_auth_failed_at == NOW  # type: ignore[union-attr]


async def test_clearing_the_sealed_value_keeps_the_user_name(db: AsyncSession, keys) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await db.commit()
    before = await raw(db, "time_tracking_user")

    await repo.clear_sealed(7)
    await db.commit()

    assert await raw(db, "time_tracking_user") == before
    db.expunge_all()
    loaded = await repo.get_by_user(7)
    assert loaded is not None
    assert loaded.time_tracking_sealed_credentials is None
    assert (
        credentials_invalid_reason(loaded, current_key_id=KEY_ID)
        is CredentialsInvalidReason.BINDING_CHANGED
    )


async def test_list_all_returns_every_holder_by_user(db: AsyncSession) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted(user_id=8, user="john.roe"))
    await repo.save(fingerprinted())
    await db.commit()

    assert [c.user_id for c in await repo.list_all()] == [7, 8]


async def test_fingerprint_lookup_and_collision(db: AsyncSession) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    saved = await repo.save(fingerprinted())
    await db.commit()
    fingerprint = saved.time_tracking_user_fingerprint

    assert await repo.is_fingerprint_taken_by_other_user(fingerprint, 8)
    assert not await repo.is_fingerprint_taken_by_other_user(fingerprint, 7)
    with pytest.raises(TimeTrackingUserAlreadyLinkedError) as exc_info:
        await repo.save(fingerprinted(user_id=8, user="JANE.DOE"))
    assert "7" not in str(exc_info.value)


async def test_delete_for_user_and_delete_all(db: AsyncSession) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await repo.save(fingerprinted(user_id=8, user="john.roe"))
    await db.commit()

    assert await repo.delete_for_user(7)
    assert not await repo.delete_for_user(7)
    assert not await repo.exists_for_user(7)
    assert await repo.delete_all() == 1
    assert await repo.get_count() == 0


# ── fingerprint ──────────────────────────────────────────────────────


def test_fingerprint_normalises_the_user_name(keys) -> None:
    assert time_tracking_fingerprint(fingerprint_subject(" Jane.Doe ")) == (
        time_tracking_fingerprint(fingerprint_subject("jane.doe"))
    )


def test_fingerprint_key_is_separate_from_the_at_rest_key(keys) -> None:
    subject = fingerprint_subject("jane.doe").encode()
    hmac_key = _derive("unit-key-a")
    at_rest_signing_key = _fernet_for("unit-key-a")._signing_key

    assert hmac_key != at_rest_signing_key
    assert time_tracking_fingerprint(subject.decode()) == (
        hmac.new(hmac_key, subject, hashlib.sha256).hexdigest()
    )
    assert time_tracking_fingerprint(subject.decode()) != (
        hmac.new(at_rest_signing_key, subject, hashlib.sha256).hexdigest()
    )


def test_fingerprint_changes_with_the_key(keys) -> None:
    subject = fingerprint_subject("jane.doe")
    before = (time_tracking_fingerprint(subject), time_tracking_fingerprint_key_id())
    keys("unit-key-b")
    after = (time_tracking_fingerprint(subject), time_tracking_fingerprint_key_id())

    assert before[0] != after[0] and before[1] != after[1]
    assert len(after[1]) == 8


async def test_boot_recomputes_fingerprints_after_a_key_rotation(db: AsyncSession, keys) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await db.commit()
    assert await recompute_time_tracking_fingerprints(db) == 0

    keys("unit-key-b", previous="unit-key-a")
    assert await reencrypt_stored_secrets(db) == 1
    db.expunge_all()
    assert await recompute_time_tracking_fingerprints(db) == 1
    keys("unit-key-b")

    db.expunge_all()
    loaded = await repo.get_by_user(7)
    assert loaded is not None
    assert loaded.time_tracking_user_fingerprint == time_tracking_fingerprint(
        fingerprint_subject("jane.doe")
    )
    assert loaded.time_tracking_user_fingerprint_key_id == time_tracking_fingerprint_key_id()
    assert loaded.time_tracking_user == "jane.doe"
    assert await recompute_time_tracking_fingerprints(db) == 0


async def test_boot_skips_rows_it_cannot_decrypt(db: AsyncSession, keys, glados_caplog) -> None:
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    await repo.save(fingerprinted())
    await db.commit()
    db.expunge_all()

    keys("unit-key-c")
    assert await recompute_time_tracking_fingerprints(db) == 0
    assert any("cannot be decrypted" in r.getMessage() for r in glados_caplog.records)
