"""
Coverage for src/modules/platform/adapters/outbound/persistence/mapping_common.py, the
shared ORM<->entity mapping helpers (creator_kwargs,
soft_delete_kwargs), extracted out of ~40-line hand-written blocks that
were duplicated across many repository mapping functions.
"""

import importlib
from datetime import UTC
from datetime import date
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import soft_delete_kwargs
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.user_loading import user_load_options

for _module_name in model_module_names():
    importlib.import_module(_module_name)


class TestSoftDeleteKwargs:
    def test_none_changes_becomes_an_empty_list(self):
        result = soft_delete_kwargs(None, None, False)
        assert result == {"changed": None, "changes": [], "deleted": False}

    def test_passes_changed_and_deleted_through(self):
        when = datetime(2026, 1, 1, tzinfo=UTC)
        result = soft_delete_kwargs(when, ["renamed"], True)
        assert result == {"changed": when, "changes": ["renamed"], "deleted": True}

    def test_accepts_a_bare_date_too(self):
        """Some aggregates (e.g. Customer) store `changed` as a Date column,
        not DateTime, datetime.datetime is a date, but a bare date must
        work too since that's the literal column type there."""
        today = date(2026, 1, 1)
        result = soft_delete_kwargs(today, [], False)
        assert result["changed"] == today

    def test_does_not_mutate_the_input_list(self):
        original = ["a", "b"]
        result = soft_delete_kwargs(None, original, False)
        result["changes"].append("c")
        assert original == ["a", "b"]


class TestCreatorKwargs:
    def setup_method(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        self.user_orm = UserOrmModel(
            username="alice",
            full_name="Alice",
            email="alice@example.com",
            created=datetime.now(UTC),
            hashed_password="x",
        )
        db.add(self.user_orm)
        db.commit()
        self.user_orm = db.scalars(
            select(UserOrmModel)
            .where(UserOrmModel.id == self.user_orm.id)
            .options(*user_load_options())
            .execution_options(populate_existing=True)
        ).one()

    def test_no_creator_returns_none(self):
        result = creator_kwargs(None, None)
        assert result == {"creator_id": None, "creator": None}

    def test_creator_id_without_a_resolved_relationship(self):
        """Mirrors an FK that points at a row not eagerly loaded, the id
        is still passed through even though there's nothing to resolve."""
        result = creator_kwargs(7, None)
        assert result == {"creator_id": 7, "creator": None}

    def test_resolves_the_creator_to_a_full_user_entity(self):
        result = creator_kwargs(self.user_orm.id, self.user_orm)

        assert result["creator_id"] == self.user_orm.id
        assert result["creator"] is not None
        assert result["creator"].username == "alice"
