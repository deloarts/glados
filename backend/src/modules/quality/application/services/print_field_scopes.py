"""
The two value scopes a docket's field map can draw from, and the one place
that knows how a source name declares which it belongs to.

- document scope: resolved once against the root DTO ("order_number",
  "@today", "@resolve_url").
- row scope: resolved once PER ROW of a positions table, against the row
  DTO ("item.quantity") or, for the per-line part photo, "@item_image".

Its own module rather than a couple of constants in print_value_resolver
so docket_spec.py can validate scoping without importing the resolver
(and the asset/renderer ports it drags in) just for a string prefix.
"""

ROW_SOURCE_PREFIX = "item."
ROW_IMAGE_SOURCE = "@item_image"


def is_row_source(source: str) -> bool:
    """True for a source that only means something in the context of one
    table row."""
    return source.startswith(ROW_SOURCE_PREFIX) or source == ROW_IMAGE_SOURCE


def row_attribute(source: str) -> str:
    """ "item.quantity" -> "quantity". Undefined for non-row sources."""
    return source.removeprefix(ROW_SOURCE_PREFIX)
