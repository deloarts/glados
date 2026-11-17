"""Template engine for ZPL label templates.

Placeholders are substituted by regex rather than str.format(), so stored
template text can never reach attribute traversal. ZPL adds its own
injection surface: `^` and `~` start commands and `,` delimits parameters.
Every ^FD field receiving a value is therefore marked with a bare ^FH and
the value's dangerous bytes become _XX hex escapes. ^FH carries no
indicator argument on purpose, so it defaults to `_`; any other indicator
would break the escapes. Literal template text is never escaped.
"""

import re

_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
# Non-greedy: a field terminates at the first ^FS, matching how ZPL fields
# are actually written (one ^FD...^FS per field, never nested). Group 1
# tolerates an already-present ^FH plus its optional single indicator-
# character argument, so a re-save doesn't double-mark a field.
_FIELD_DATA_RE = re.compile(r"(\^FH[^\^~]?)?(\^FD)(.*?)(\^FS)", re.DOTALL)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f]")

# _ is escaped too: it is ^FH's own hex-indicator character, so a literal
# underscore in data would otherwise risk being misread as the start of a
# _XX escape sequence once other bytes in the same field are escaped.
_ZPL_ESCAPES = {"^": "_5E", "~": "_7E", ",": "_2C", "_": "_5F"}
_ZPL_ESCAPE_RE = re.compile("|".join(re.escape(c) for c in _ZPL_ESCAPES))


def zpl_escape(value: str) -> str:
    """Escapes a value for a ^FH-marked ^FD field: control characters are
    stripped and ^ ~ , _ become hex escapes."""
    stripped = _CONTROL_CHARS_RE.sub("", value)
    return _ZPL_ESCAPE_RE.sub(lambda m: _ZPL_ESCAPES[m.group(0)], stripped)


def validate_zpl_template(zpl: str, field_map: dict[str, str]) -> None:
    """Raises ValueError for a malformed template or a placeholder missing
    from field_map."""
    if not zpl or not zpl.strip():
        raise ValueError("ZPL template must not be empty.")
    if "^XA" not in zpl or "^XZ" not in zpl:
        raise ValueError("ZPL template must contain ^XA ... ^XZ.")

    missing = placeholders_in(zpl) - field_map.keys()
    if missing:
        raise ValueError(
            f"Template references unmapped placeholder(s): {', '.join(sorted(missing))}."
        )


def placeholders_in(zpl: str) -> set[str]:
    """Every {placeholder} name referenced in the template."""
    return set(_PLACEHOLDER_RE.findall(zpl))


def _mark_hex_fields(zpl: str) -> str:
    """Prefixes every ^FD block containing a placeholder with a bare ^FH,
    unless it already has one."""

    def _mark(m: re.Match[str]) -> str:
        fh, fd, body, fs = m.group(1), m.group(2), m.group(3), m.group(4)
        if fh or not _PLACEHOLDER_RE.search(body):
            return m.group(0)
        return f"^FH{fd}{body}{fs}"

    return _FIELD_DATA_RE.sub(_mark, zpl)


def render_zpl(zpl: str, values: dict[str, str]) -> str:
    """Substitutes placeholders, escaping values that land in a ^FD field."""
    marked = _mark_hex_fields(zpl)

    def _sub_in_field(m: re.Match[str]) -> str:
        fh, fd, body, fs = m.group(1), m.group(2), m.group(3), m.group(4)
        body = _PLACEHOLDER_RE.sub(lambda pm: zpl_escape(values.get(pm.group(1), "")), body)
        return f"{fh or ''}{fd}{body}{fs}"

    substituted = _FIELD_DATA_RE.sub(_sub_in_field, marked)
    # A placeholder outside any ^FD...^FS block is not field data (should
    # not occur in a well-formed template); substituted unescaped.
    return _PLACEHOLDER_RE.sub(lambda pm: values.get(pm.group(1), ""), substituted)
