"""
The changer of a row, the user behind its latest `changed` timestamp, shared
by every table that records one. A model mixes in ChangedByColumns next to
its own `changed` column; the constraint is named after the table.

Nobody sets the changer by hand. The session listener in
`persistence/changer_tracking.py` fills it whenever a flush moves `changed`.
"""

from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import declared_attr
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

_USER_MODEL = "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel"


def _changed_by_fk(cls: Any) -> Mapped[Any]:
    return mapped_column(
        Integer,
        ForeignKey("user_table.id", name=f"fk_{cls.__tablename__}_changed_by_id"),
        nullable=True,
        index=True,
    )


def _changed_by(cls: Any) -> Mapped[Any]:
    return relationship(_USER_MODEL, foreign_keys=[cls.changed_by_id], lazy="raise_on_sql")


class ChangedByColumns:
    @declared_attr
    def changed_by_id(cls) -> Mapped[int | None]:
        return _changed_by_fk(cls)

    @declared_attr
    def changed_by(cls) -> Mapped["UserOrmModel | None"]:
        return _changed_by(cls)
