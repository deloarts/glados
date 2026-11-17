"""
Coverage for the O(1) RFID lookup: the HMAC function in
src/modules/platform/infrastructure/security/rfid.py, and
SqlAlchemyUserRepository.get_by_rfid's indexed query against real SQL,
which a fake in-memory repository cannot exercise.
"""

import hashlib
import importlib
from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.infrastructure.security.rfid import rfid_lookup

for _module_name in model_module_names():
    importlib.import_module(_module_name)


class TestRfidLookupFunction:
    def test_deterministic(self):
        assert rfid_lookup("tag-1") == rfid_lookup("tag-1")

    def test_different_tags_produce_different_lookups(self):
        assert rfid_lookup("tag-1") != rfid_lookup("tag-2")

    def test_not_a_plain_hash_of_the_tag(self):
        """The whole point of the pepper: a plain SHA-256 of the tag value
        must not appear anywhere in the output, or an attacker with a DB
        dump could rebuild the index without the app secret."""
        assert rfid_lookup("tag-1") != hashlib.sha256(b"tag-1").hexdigest()

    def test_depends_on_the_configured_secret(self, monkeypatch):
        from src.modules.platform.infrastructure.config.settings import cfg

        before = rfid_lookup("tag-1")
        monkeypatch.setattr(cfg.security, "secret_key_persistent", "a-different-secret")
        after = rfid_lookup("tag-1")
        assert before != after


class TestGetByRfid:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.db = async_sessionmaker(engine, expire_on_commit=False)()
        self.repo = SqlAlchemyUserRepository(self.db)
        yield
        await self.db.close()
        await engine.dispose()

    async def _add_user(self, *, username, rfid_lookup_value=None, is_active=True):
        orm = UserOrmModel(
            username=username,
            full_name=username,
            email=f"{username}@example.com",
            created=datetime.now(UTC),
            hashed_password="x",
            rfid_lookup=rfid_lookup_value,
            is_active=is_active,
        )
        self.db.add(orm)
        await self.db.commit()
        await self.db.refresh(orm)
        # Detached, so the repository loads its own instance with members,
        # as it does on a request's fresh session; a refreshed instance held
        # in the identity map would carry an unloaded raise_on_sql relationship.
        self.db.expunge(orm)
        return orm

    async def test_indexed_match_returns_the_user(self):
        await self._add_user(username="tagged", rfid_lookup_value=rfid_lookup("tag-1"))

        found = await self.repo.get_by_rfid("tag-1")

        assert found is not None
        assert found.username == "tagged"

    async def test_unknown_tag_returns_none(self):
        await self._add_user(username="someone", rfid_lookup_value=rfid_lookup("tag-1"))

        assert await self.repo.get_by_rfid("no-such-tag") is None

    async def test_inactive_indexed_user_is_excluded(self):
        await self._add_user(
            username="inactive", rfid_lookup_value=rfid_lookup("tag-1"), is_active=False
        )

        assert await self.repo.get_by_rfid("tag-1") is None
