"""
Links one PDM document file to the made/bought item file it was stored
as. No config imports.
"""

from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class PdmDocumentLinkOrmModel(Base):
    __tablename__ = "pdm_document_link_table"

    __table_args__ = (
        Index(
            "uq_pdm_document_link_vault_file",
            "vault_id",
            "file_id",
            unique=True,
        ),
        Index("ix_pdm_document_link_item_file_id", "item_file_id"),
        Index("ix_pdm_document_link_item_picture_id", "item_picture_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    kind: Mapped[str] = mapped_column(String, nullable=False)  # "made" | "bought"
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vault_id: Mapped[str] = mapped_column(String, nullable=False)
    file_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    item_picture_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
