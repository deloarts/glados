"""
Several-PDM-users-to-one-Glados-user mapping, see UserPdmLink's docstring.
No config imports.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class UserPdmLinkOrmModel(Base):
    __tablename__ = "user_pdm_link_table"

    __table_args__ = (UniqueConstraint("pdm_user_id", name="uq_user_pdm_link_table_pdm_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_user_pdm_link_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )
    pdm_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    pdm_username: Mapped[str] = mapped_column(String, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
