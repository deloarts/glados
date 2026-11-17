"""
Domain entity for the order and bought item settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminOrderSettings(Entity):
    """Settings for the Order domain (bought-item catalogue, orders, demands, allocations).

    Part numbers are unique across the whole application.
    pdm_part_number_pattern below marks the numbers reserved for PDM ingest.
    """

    order_number_format: str  # e.g. "ORD-{yy}-{seq:05d}"; {seq} must be the last token
    part_number_format: str  # e.g. "PUR-{yy}-{seq:05d}"; {seq} must be the last token
    part_number_auto: bool  # generate the part number on creation instead of manual entry
    part_number_editable: bool  # whether a user may change the part number after creation
    # Whether web creation of bought items is allowed when the PDM
    # integration is enabled, effective only once is_pdm_enabled()
    # (application.services.pdm_integration) is True.
    web_creation_allowed: bool
    # Regex matched against a hand-typed part number; "" = no external
    # pattern configured, nothing is reserved for PDM ingest.
    pdm_part_number_pattern: str
    # How far a delivery on a supplier line that is not a MADE line may go
    # beyond or stay below the ordered quantity, in percent of it; a
    # catalogue item's own value replaces these. 0 takes exactly the ordered
    # quantity.
    over_delivery_tolerance_percent: float = 0.0
    under_delivery_tolerance_percent: float = 0.0
    # e.g. "RFQ-{yy}-{seq:05d}"; numbers the quote requests sent to suppliers.
    quote_request_number_format: str = "RFQ-{yy}-{seq:05d}"
