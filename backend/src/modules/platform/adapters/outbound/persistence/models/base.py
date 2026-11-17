"""
Declarative base for all SQLAlchemy ORM models.
Imported by every ORM model and by alembic_imports.py.
"""

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    # Globally unique, opaque row identifier, safe to expose externally (e.g.
    # QR codes) without leaking sequential `id` volume. Python-side default so
    # it's populated on SQLite (tests) as well as Postgres, and so bare
    # `OrmModel(...)` construction (not just repository .save()) gets one.
    # Never add this to a repository's entity->dict update payload: that dict
    # is shared between insert and update, and doing so would rotate the
    # value on every save.
    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), nullable=False, unique=True, index=True, default=uuid.uuid4
    )
