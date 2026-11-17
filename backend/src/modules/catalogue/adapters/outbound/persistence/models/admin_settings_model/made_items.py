"""
ORM model for the admin_made_item_settings singleton table, plus the
revision field policy default it uses as both Python and server default.
"""

import json

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.platform.adapters.outbound.persistence.models.base import Base


def _revision_field_policy_default() -> list[dict[str, bool | str]]:
    """default_policy(), serialised the way revision_field_policy
    stores it. Used both as the Python-side `default` (rows created
    through the ORM) and, via json.dumps below, as the column's
    `server_default` (rows inserted without the ORM)."""
    return [
        {
            "field": p.field,
            "web_requires_revision": p.web_requires_revision,
            "pdm_update_in_place": p.pdm_update_in_place,
        }
        for p in default_policy()
    ]


_REVISION_FIELD_POLICY_SERVER_DEFAULT = json.dumps(_revision_field_policy_default())


class AdminMadeItemSettingsOrmModel(Base):
    __tablename__ = "admin_made_item_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    item_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="FAB-{yy}-{seq:05d}"
    )
    lot_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="LOT-{yy}-{seq:05d}"
    )
    calculation_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="CAL-{yy}-{seq:04d}"
    )
    checklist_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="CHK-{yy}-{seq:04d}"
    )
    sequence_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="SEQ-{yy}-{seq:04d}"
    )
    meeting_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="MTG-{yy}-{seq:04d}"
    )
    part_number_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    part_number_editable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # part_number_source / part_number_unique removed, see the note on
    # AdminOrderSettingsOrmModel (orders.py), same reasoning, same rework.

    # ── Revisions ─────────────────────────────────────
    revision_start: Mapped[str] = mapped_column(
        String, nullable=False, server_default="0"
    )  # one of revision_scheme.START_REVISIONS
    revision_separator: Mapped[str] = mapped_column(
        String, nullable=False, server_default=":"
    )  # free text, display only, no validation
    revision_skip_ambiguous_letters: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    revision_only_newest_editable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    revision_predecessor_status_web: Mapped[str] = mapped_column(
        String, nullable=False, server_default="ask"
    )  # "ask" | a MadeItemCatalogueStatus value
    revision_predecessor_status_pdm: Mapped[str] = mapped_column(
        String, nullable=False, server_default="replaced"
    )  # a MadeItemCatalogueStatus value, no "ask" (no user to ask)
    # One row per REVISION_POLICY_FIELDS entry, {field,
    # web_requires_revision, pdm_update_in_place}. default_policy() is also
    # the server_default below (JSON.dumps of the same list), so a row
    # starts identical whether or not the ORM inserted it.
    revision_field_policy: Mapped[list[dict[str, bool | str]]] = mapped_column(
        JSON,
        nullable=False,
        default=_revision_field_policy_default,
        server_default=_REVISION_FIELD_POLICY_SERVER_DEFAULT,
    )

    # Same fields and reasoning as AdminOrderSettingsOrmModel (orders.py).
    web_creation_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    pdm_part_number_pattern: Mapped[str] = mapped_column(String, nullable=False, server_default="")
