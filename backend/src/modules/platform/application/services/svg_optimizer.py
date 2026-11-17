"""
Makes a cleaned SVG cheaper to parse and to draw without changing what it
shows. CAD exports of an overview drawing carry thousands of small paths
with coordinates printed to fifteen digits, and the browser parses and
redraws all of them on every zoom, so the upload is slimmed once instead.

The optimizer works on the sanitizer's output and, apart from the page
background, only makes changes that leave the picture as it was. It drops a
background colour set on the drawing itself, since the overview canvas
supplies its own and a drawing exported on white would hide it. It rounds
coordinates in path data, point lists, transforms and plain numeric
attributes to six significant digits, which keeps the error a millionth of
each value whatever unit the drawing uses. It drops the whitespace between
elements, unwraps groups that carry no attributes and removes empty ones.
It removes elements switched off with `display: none` unless something
inside them has an id another element may reference.

The largest saving for a line drawing comes from joining. Neighbouring
groups with identical attributes become one group, and inside a group whose
fill is `none`, whether set on the path or inherited, runs of sibling
paths with identical attributes become one path. Plain circles and ellipses
there are first written as paths so they join as well. Dashes restart at
each subpath, so a joined path looks the same. Paths with markers, opacity
or an id are left alone, groups with opacity, a mask or a filter are not
joined because their content is composited as a whole, and when the drawing
has a style sheet, which could restyle any element, neither the hidden
elements nor the paths and groups are touched.
"""

import math
import re
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET

from src.modules.platform.application.services.svg_sanitizer import SVG_NS
from src.modules.platform.application.services.svg_sanitizer import XLINK_NS

SIGNIFICANT_DIGITS = 6

# Elements whose text is content, so whitespace inside them is kept.
_TEXT_ELEMENTS = frozenset({"text", "tspan", "textPath", "style", "title", "desc"})
# Elements whose content is only drawn when referenced, never on its own.
_REFERENCED_CONTAINERS = frozenset({"defs", "symbol", "clipPath", "mask", "pattern", "marker"})
_NUMERIC_ATTRIBUTES = frozenset(
    {"x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry"}
    | {"width", "height", "stroke-width"}
)
# Inherited properties that make joined paths look different from separate
# ones, wherever they are set.
_INHERITED_UNMERGEABLE = frozenset(
    {"stroke-opacity", "marker", "marker-start", "marker-mid", "marker-end"}
)
# Attributes that make joined paths look different from separate ones when
# set on a path itself.
_UNMERGEABLE_ATTRIBUTES = _INHERITED_UNMERGEABLE | {"id", "opacity", "pathLength", "mask", "filter"}
# Attributes that make a group's content composited as a whole, so two such
# groups cannot become one.
_COMPOSITED_GROUP_ATTRIBUTES = frozenset({"id", "opacity", "mask", "filter"})
# The attributes a circle or ellipse may carry to be written as a path.
_SHAPE_GEOMETRY = {
    "circle": frozenset({"cx", "cy", "r"}),
    "ellipse": frozenset({"cx", "cy", "rx", "ry"}),
}

_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_PLAIN_NUMBER = re.compile(r"\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?\s*")
_SEPARATORS = re.compile(r"[\s,]+")
_FLAG = re.compile(r"[01]")
# The number of arguments each path command takes per repetition.
_PATH_ARITY = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
# The large arc and sweep flags of an arc, which may be written without separators.
_ARC_FLAGS = (3, 4)

PathCommand = tuple[str, list[str]]


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _round(number: str) -> str:
    """The number to six significant digits in its shortest form."""
    value = float(number)
    if not math.isfinite(value):
        return number
    text = f"{value:.{SIGNIFICANT_DIGITS}g}"
    if text in ("-0", "0"):
        return "0"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def _join_numbers(numbers: list[str]) -> str:
    """The numbers separated by a space, or by nothing before a minus sign."""
    parts: list[str] = []
    for index, number in enumerate(numbers):
        if index > 0 and not number.startswith("-"):
            parts.append(" ")
        parts.append(number)
    return "".join(parts)


def _skip_separators(d: str, pos: int) -> int:
    match = _SEPARATORS.match(d, pos)
    return match.end() if match else pos


def _parse_path(d: str) -> list[PathCommand] | None:
    """The commands of path data with their arguments, or None when the data
    is malformed and must be left exactly as it is."""
    commands: list[PathCommand] = []
    pos = _skip_separators(d, 0)
    while pos < len(d):
        command = d[pos]
        read = _read_arguments(d, pos + 1, command)
        if read is None:
            return None
        args, pos = read
        commands.append((command, args))
        pos = _skip_separators(d, pos)
    return commands


def _read_arguments(d: str, pos: int, command: str) -> tuple[list[str], int] | None:
    """The arguments of a command from `pos` on, as many repetitions as follow
    before the next command, and the position after them. None when the
    command is unknown or its arguments are incomplete."""
    arity = _PATH_ARITY.get(command.lower())
    if arity is None:
        return None
    args: list[str] = []
    while arity:
        pos = _skip_separators(d, pos)
        if pos >= len(d) or d[pos].lower() in _PATH_ARITY:
            break
        end = _read_repetition(d, pos, command, args)
        if end is None:
            return None
        pos = end
    if arity and not args:
        return None
    return args, pos


def _read_repetition(d: str, pos: int, command: str, args: list[str]) -> int | None:
    """Appends one set of the command's arguments to `args` and returns the
    position after it, or None when the set is incomplete."""
    for index in range(_PATH_ARITY[command.lower()]):
        pos = _skip_separators(d, pos)
        pattern = _FLAG if command.lower() == "a" and index in _ARC_FLAGS else _NUMBER
        match = pattern.match(d, pos)
        if match is None:
            return None
        args.append(match.group())
        pos = match.end()
    return pos


def _format_path(commands: list[PathCommand]) -> str:
    return "".join(command + _join_numbers(args) for command, args in commands)


def _round_path(commands: list[PathCommand]) -> list[PathCommand]:
    return [(command, [_round(arg) for arg in args]) for command, args in commands]


def _as_continuation(commands: list[PathCommand]) -> list[PathCommand]:
    """The commands of a path rewritten to continue another one. A path's
    first moveto is absolute even when written as `m`, and the pairs after
    it are relative linetos, which an `M` and an `l` say explicitly."""
    if not commands or commands[0][0] != "m":
        return commands
    _, args = commands[0]
    rest: list[PathCommand] = [("l", args[2:])] if len(args) > 2 else []
    return [("M", args[:2]), *rest, *commands[1:]]


def _style(element: ET.Element) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for declaration in element.get("style", "").split(";"):
        name, _, value = declaration.partition(":")
        if name.strip():
            declarations[name.strip().lower()] = value.strip().lower()
    return declarations


def _is_hidden(element: ET.Element) -> bool:
    return element.get("display", "").strip() == "none" or _style(element).get("display") == "none"


def _has_id(element: ET.Element) -> bool:
    return any("id" in node.attrib for node in element.iter())


def _sets_any(element: ET.Element, names: frozenset[str]) -> bool:
    style = _style(element)
    return any(name in element.attrib or name in style for name in names)


class _Outline:
    """What an element passes on to its children that decides whether their
    paths may be joined: whether the fill is `none`, and whether a property
    that forbids joining is inherited."""

    def __init__(self, fill_none: bool = False, blocked: bool = False) -> None:
        self.fill_none = fill_none
        self.blocked = blocked

    def within(self, element: ET.Element) -> "_Outline":
        fill = _style(element).get("fill", element.get("fill"))
        fill_none = (
            self.fill_none if fill is None or fill.strip() == "inherit" else fill.strip() == "none"
        )
        return _Outline(fill_none, self.blocked or _sets_any(element, _INHERITED_UNMERGEABLE))


def _is_outline_path(element: ET.Element, outline: _Outline) -> bool:
    """Whether the element is a path drawn as an outline only, with nothing
    that would look different once it is joined with its neighbours."""
    if _local(element.tag) != "path" or len(element) or "d" not in element.attrib:
        return False
    own = outline.within(element)
    return own.fill_none and not own.blocked and not _sets_any(element, _UNMERGEABLE_ATTRIBUTES)


def _same_drawing(a: ET.Element, b: ET.Element) -> bool:
    return {k: v for k, v in a.attrib.items() if k != "d"} == {
        k: v for k, v in b.attrib.items() if k != "d"
    }


def _shape_as_path(element: ET.Element) -> None:
    """Writes a plain circle or ellipse as the same outline in a path, two
    half arcs from its leftmost point, so it can join its neighbours."""
    geometry = _SHAPE_GEOMETRY.get(_local(element.tag))
    if geometry is None or set(element.attrib) - geometry or len(element):
        return
    values: dict[str, float] = {}
    for name in geometry:
        value = element.get(name, "0")
        if not _PLAIN_NUMBER.fullmatch(value):
            return
        values[name] = float(value)
    rx = values.get("r", values.get("rx", 0.0))
    ry = values.get("r", values.get("ry", 0.0))
    if rx <= 0 or ry <= 0:
        return
    start = [_round(str(values.get("cx", 0.0) - rx)), _round(str(values.get("cy", 0.0)))]
    radii = [_round(str(rx)), _round(str(ry))]
    commands: list[PathCommand] = [
        ("M", start),
        ("a", [*radii, "0", "1", "0", _round(str(2 * rx)), "0"]),
        ("a", [*radii, "0", "1", "0", _round(str(-2 * rx)), "0"]),
        ("z", []),
    ]
    element.tag = f"{{{SVG_NS}}}path"
    element.attrib.clear()
    element.set("d", _format_path(commands))


def _merge_groups(element: ET.Element) -> None:
    """Joins runs of sibling groups with identical attributes, which draw
    exactly as one group holding both contents."""
    index = 1
    while index < len(element):
        previous, child = element[index - 1], element[index]
        if (
            _local(previous.tag) == "g"
            and _local(child.tag) == "g"
            and previous.attrib == child.attrib
            and not (previous.tail or "").strip()
            and not _sets_any(previous, _COMPOSITED_GROUP_ATTRIBUTES)
        ):
            previous.extend(list(child))
            previous.tail = child.tail
            del element[index]
            continue
        index += 1


def _round_attributes(element: ET.Element) -> None:
    local = _local(element.tag)
    for name, value in list(element.attrib.items()):
        if name == "d" and local == "path":
            commands = _parse_path(value)
            if commands is not None:
                element.set(name, _format_path(_round_path(commands)))
        elif name == "points":
            element.set(name, _join_numbers([_round(n) for n in _NUMBER.findall(value)]))
        elif name in ("transform", "gradientTransform", "patternTransform"):
            element.set(name, _NUMBER.sub(lambda m: _round(m.group()), value))
        elif name in _NUMERIC_ATTRIBUTES and _PLAIN_NUMBER.fullmatch(value):
            element.set(name, _round(value.strip()))


def _merge_paths(element: ET.Element, outline: _Outline) -> None:
    """Joins runs of sibling outline paths with identical attributes. Each
    path is parsed once and every joined path is written once, so a group
    of thousands of paths takes linear time."""
    if outline.fill_none and not outline.blocked:
        for child in element:
            _shape_as_path(child)
    kept: list[ET.Element] = []
    run: list[PathCommand] = []
    run_head: ET.Element | None = None
    for child in list(element):
        commands = _parse_path(child.get("d", "")) if _is_outline_path(child, outline) else None
        if (
            commands is not None
            and run_head is not None
            and not (run_head.tail or "").strip()
            and _same_drawing(run_head, child)
        ):
            run.extend(_as_continuation(commands))
            run_head.tail = child.tail
            continue
        if run_head is not None:
            run_head.set("d", _format_path(run))
        run_head, run = (child, commands) if commands is not None else (None, [])
        kept.append(child)
    if run_head is not None:
        run_head.set("d", _format_path(run))
    element[:] = kept


def _optimize(element: ET.Element, outline: _Outline, *, in_reference: bool, styled: bool) -> None:
    local = _local(element.tag)
    in_reference = in_reference or local in _REFERENCED_CONTAINERS
    outline = outline.within(element)
    if local not in _TEXT_ELEMENTS:
        _drop_layout_whitespace(element)
    if not styled:
        _merge_groups(element)
    _optimize_children(element, outline, in_reference=in_reference, styled=styled)
    _round_attributes(element)
    if not styled:
        _merge_paths(element, outline)


def _drop_layout_whitespace(element: ET.Element) -> None:
    """Removes the whitespace that only lays out the source, before the first
    child and after each one."""
    if element.text is not None and not element.text.strip():
        element.text = None
    for child in element:
        if child.tail is not None and not child.tail.strip():
            child.tail = None


def _optimize_children(
    element: ET.Element, outline: _Outline, *, in_reference: bool, styled: bool
) -> None:
    """Drops the hidden children, optimizes the others and then removes or
    unwraps the groups that are left empty or bare."""
    index = 0
    while index < len(element):
        child = element[index]
        if not styled and not in_reference and _is_hidden(child) and not _has_id(child):
            del element[index]
            continue
        _optimize(child, outline, in_reference=in_reference, styled=styled)
        index = _settle_group(element, index)


def _settle_group(element: ET.Element, index: int) -> int:
    """Removes the child at `index` when it is an empty group without an id
    and unwraps it when it is a group without attributes. Returns the index
    of the next child to visit."""
    child = element[index]
    if _local(child.tag) != "g":
        return index + 1
    if not len(child) and "id" not in child.attrib:
        del element[index]
        return index
    if child.attrib:
        return index + 1
    # A group without attributes changes nothing about its content.
    grandchildren = list(child)
    if grandchildren and child.tail:
        grandchildren[-1].tail = (grandchildren[-1].tail or "") + child.tail
    del element[index]
    for offset, grandchild in enumerate(grandchildren):
        element.insert(index + offset, grandchild)
    return index + len(grandchildren)


def _drop_background(root: ET.Element) -> None:
    """Removes a background colour set in the drawing's own style."""
    style = root.get("style")
    if style is None:
        return
    kept = [
        declaration.strip()
        for declaration in style.split(";")
        if declaration.strip()
        and declaration.partition(":")[0].strip().lower() not in ("background", "background-color")
    ]
    if kept:
        root.set("style", "; ".join(kept))
    else:
        del root.attrib["style"]


def optimize_svg(data: bytes) -> bytes:
    """The drawing slimmed for display, UTF-8 encoded. Expects the output of
    `sanitize_svg`, which has already refused anything malformed."""
    root = DefusedET.fromstring(data)
    styled = any(_local(node.tag) == "style" for node in root.iter())
    _drop_background(root)
    _optimize(root, _Outline(), in_reference=False, styled=styled)

    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    optimized: bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return optimized
