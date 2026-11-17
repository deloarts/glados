"""
Catalogue labels in tool results. Article groups, source item types and
fabrication and inspection methods carry their name and description as a
map from language code to text, and so do the flattened names on items,
lot steps and QA tasks. An agent gets each of them as one string in the
acting user's language (see infrastructure/label_languages.py), the same
fallback the web app shows.
"""

from typing import Any

from src.modules.platform.infrastructure.label_languages import resolve_label

# Keys whose value is a catalogue label when it is a language map. A plain
# string under one of them, such as a supplier's name, is left as it is.
_LABEL_FIELDS = frozenset(
    {"name", "description", "type_name", "fabrication_method_name", "inspection_method_name"}
)


def resolved_labels(data: Any) -> Any:
    """JSON-shaped `data` with every label map, at any depth, resolved to
    one string."""
    if isinstance(data, dict):
        return {
            key: resolve_label(value)
            if key in _LABEL_FIELDS and isinstance(value, dict)
            else resolved_labels(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [resolved_labels(value) for value in data]
    return data
