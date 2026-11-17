"""
ORM model for the admin_order_settings singleton table.
"""

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.percent_type import PercentType


class AdminOrderSettingsOrmModel(Base):
    __tablename__ = "admin_order_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    order_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="ORD-{yy}-{seq:05d}"
    )
    part_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="PUR-{yy}-{seq:05d}"
    )
    part_number_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    part_number_editable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Part numbers are unique across the whole application via
    # part_number_registry, and pdm_part_number_pattern below marks the
    # numbers reserved for PDM ingest.
    #
    # Web creation of bought items while the PDM integration is
    # enabled is an admin choice, effective only once is_pdm_enabled()
    # (application.services.pdm_integration) is True.
    web_creation_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # Regex matched against a hand-typed part number; "" (default) =
    # no external pattern configured, nothing is reserved for PDM ingest.
    pdm_part_number_pattern: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    # How far a delivery may go beyond or stay below the ordered quantity of
    # a supplier line that is not a MADE line, in percent of it; a catalogue
    # item's own value replaces these. 0 takes exactly the ordered quantity.
    over_delivery_tolerance_percent: Mapped[float] = mapped_column(
        PercentType, nullable=False, server_default="0"
    )
    under_delivery_tolerance_percent: Mapped[float] = mapped_column(
        PercentType, nullable=False, server_default="0"
    )
    # Numbers the quote requests sent to suppliers; {seq} is the last token.
    quote_request_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="RFQ-{yy}-{seq:05d}"
    )
