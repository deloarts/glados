"""
A supplier's EPLAN Data Portal code is the manufacturer short name the
portal uses (SIE for Siemens, FES for Festo). It is how a part from the
portal finds its Glados manufacturer, so it is stored trimmed and upper
case, and at most one live supplier carries a code.
"""

import re

from src.modules.catalogue.domain.errors import SupplierEdpCodeInvalidError

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{0,15}$")


def normalize_edp_code(value: str | None) -> str | None:
    """None or blank means no code; anything else must be a short code of
    letters, digits, dot, dash or underscore."""
    if value is None or not value.strip():
        return None
    code = value.strip().upper()
    if not _CODE.match(code):
        raise SupplierEdpCodeInvalidError(
            f"{value!r} is not a Data Portal manufacturer code (letters and digits, up to 16)."
        )
    return code
