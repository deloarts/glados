from xml.etree import ElementTree as ET

from src.modules.platform.application.services.svg_optimizer import optimize_svg
from src.modules.platform.application.services.svg_sanitizer import SVG_NS

NS = f'xmlns="{SVG_NS}" xmlns:xlink="http://www.w3.org/1999/xlink"'
OUTLINE = 'fill="none" stroke="#000" stroke-width="0.5"'


def _optimize(body: str) -> ET.Element:
    data = optimize_svg(f'<svg {NS} viewBox="0 0 100 100">{body}</svg>'.encode())
    return ET.fromstring(data)


def _children(root: ET.Element) -> list[ET.Element]:
    return list(root)


def _tag(element: ET.Element) -> str:
    return element.tag.split("}")[1]


def test_svg_optimizer_rounds_coordinates_to_six_significant_digits() -> None:
    root = _optimize(
        '<path fill="red" d="M10.123456789 0.000123456789L-0.5000001 20"/>'
        '<polygon points="1.23456789,2 3,4.00000001"/>'
        '<rect x="12.3456789" width="10mm" transform="matrix(1.0000000001 0 0 1 0.33333333 0)"/>'
    )
    path, polygon, rect = _children(root)
    assert path.get("d") == "M10.1235 .000123457L-.5 20"
    assert polygon.get("points") == "1.23457 2 3 4"
    assert rect.get("x") == "12.3457"
    assert rect.get("width") == "10mm"
    assert rect.get("transform") == "matrix(1 0 0 1 .333333 0)"
    assert root.get("viewBox") == "0 0 100 100"


def test_svg_optimizer_reads_arc_flags_written_without_separators() -> None:
    root = _optimize('<path fill="red" d="M0 0a10 10 0 0110 10.0000001"/>')
    assert _children(root)[0].get("d") == "M0 0a10 10 0 0 1 10 10"


def test_svg_optimizer_leaves_malformed_path_data_alone() -> None:
    root = _optimize(f'<path {OUTLINE} d="M0 0 L 5 x"/><path {OUTLINE} d="M1 1L2 2"/>')
    paths = _children(root)
    assert [p.get("d") for p in paths] == ["M0 0 L 5 x", "M1 1L2 2"]


def test_svg_optimizer_joins_outline_paths_with_identical_attributes() -> None:
    root = _optimize(
        f'<path {OUTLINE} d="M0 0L10 0"/>\n  <path {OUTLINE} d="m5 5 1 1 2 2"/>'
        f'<path fill="none" stroke="#f00" d="M0 0L1 1"/>'
    )
    joined, other = _children(root)
    assert joined.get("d") == "M0 0L10 0M5 5l1 1 2 2"
    assert other.get("stroke") == "#f00"


def test_svg_optimizer_keeps_filled_marked_and_identified_paths_apart() -> None:
    root = _optimize(
        '<path fill="red" d="M0 0L1 0"/><path fill="red" d="M0 1L1 1"/>'
        f'<path {OUTLINE} marker-end="url(#m)" d="M0 2L1 2"/>'
        f'<path {OUTLINE} marker-end="url(#m)" d="M0 3L1 3"/>'
        f'<path {OUTLINE} id="a" d="M0 4L1 4"/><path {OUTLINE} id="b" d="M0 5L1 5"/>'
    )
    assert len(_children(root)) == 6


def test_svg_optimizer_unwraps_bare_groups_and_drops_empty_ones() -> None:
    root = _optimize(
        f'<g><g><path {OUTLINE} d="M0 0L1 1"/></g></g>'
        '<g transform="scale(2)"><rect width="1"/></g><g/>'
    )
    children = _children(root)
    assert [_tag(c) for c in children] == ["path", "g"]
    assert children[1].get("transform") == "scale(2)"


def test_svg_optimizer_drops_hidden_elements_unless_referenced() -> None:
    root = _optimize(
        '<g display="none"><rect width="1"/></g>'
        '<g style="display: none"><circle r="1"/></g>'
        '<g display="none"><path id="kept" d="M0 0L1 1"/></g>'
        '<defs><rect display="none" width="2"/></defs>'
        '<use xlink:href="#kept"/>'
    )
    tags = [_tag(c) for c in _children(root)]
    assert tags == ["g", "defs", "use"]
    defs = root.find(f"{{{SVG_NS}}}defs")
    assert defs is not None
    assert len(defs) == 1


def test_svg_optimizer_leaves_paths_and_hidden_elements_alone_under_a_style_sheet() -> None:
    root = _optimize(
        "<style>.a { display: inline }</style>"
        '<g class="a" display="none"><rect width="1"/></g>'
        f'<path {OUTLINE} d="M0 0L1 0"/><path {OUTLINE} d="M0 1L1 1"/>'
    )
    assert [_tag(c) for c in _children(root)] == ["style", "g", "path", "path"]


def test_svg_optimizer_keeps_whitespace_inside_text() -> None:
    root = _optimize('<text x="1">  two  words </text>\n\n<rect width="1"/>')
    text = _children(root)[0]
    assert text.text == "  two  words "
    assert text.tail is None


def test_svg_optimizer_drops_the_drawings_own_background() -> None:
    style = "background : rgb(255,255,255); color: red"
    data = optimize_svg(f'<svg {NS} style="{style}"><rect width="1"/></svg>'.encode())
    assert ET.fromstring(data).get("style") == "color: red"
    plain = optimize_svg(
        f'<svg {NS} style="background-color: #fff"><rect width="1"/></svg>'.encode()
    )
    assert ET.fromstring(plain).get("style") is None


def test_svg_optimizer_joins_paths_and_circles_that_inherit_an_outline() -> None:
    root = _optimize(
        '<g fill="none" stroke="#000">'
        '<path d="M0 0L1 0"/><circle cx="5" cy="5" r="2"/><path d="m1 1 2 2"/>'
        '<circle cx="1" cy="1" r="1" stroke="red"/>'
        "</g>"
    )
    group = _children(root)[0]
    assert [_tag(c) for c in group] == ["path", "circle"]
    assert group[0].get("d") == "M0 0L1 0M3 5a2 2 0 1 0 4 0a2 2 0 1 0-4 0zM1 1l2 2"


def test_svg_optimizer_keeps_filled_or_marked_inherited_paths_apart() -> None:
    root = _optimize(
        '<g stroke="#000"><path d="M0 0L1 0"/><path d="M0 1L1 1"/></g>'
        '<g fill="none" stroke-opacity="0.5"><path d="M0 0L1 0"/><path d="M0 1L1 1"/></g>'
    )
    assert [len(g) for g in _children(root)] == [2, 2]


def test_svg_optimizer_joins_neighbouring_groups_with_identical_attributes() -> None:
    root = _optimize(
        '<g fill="none" stroke="#000"><path d="M0 0L1 0"/></g>'
        '<g fill="none" stroke="#000"><path d="M0 1L1 1"/></g>'
        '<g fill="none" stroke="#f00"><path d="M0 2L1 2"/></g>'
        '<g opacity="0.5"><rect width="1"/></g><g opacity="0.5"><rect width="2"/></g>'
    )
    groups = _children(root)
    assert len(groups) == 4
    assert groups[0][0].get("d") == "M0 0L1 0M0 1L1 1"
    assert groups[1].get("stroke") == "#f00"


def test_svg_optimizer_keeps_whitespace_between_the_parts_of_a_text() -> None:
    root = _optimize("<text>a <tspan>b</tspan> <tspan>c</tspan>\n</text>")
    text = _children(root)[0]
    assert text.text == "a "
    assert [t.tail for t in text] == [" ", "\n"]


def test_svg_optimizer_keeps_text_and_tails_that_are_not_whitespace() -> None:
    root = _optimize('<g fill="red">x<rect width="1"/>y<rect width="2"/> </g>')
    group = _children(root)[0]
    assert group.text == "x"
    assert [r.tail for r in group] == ["y", None]


def test_svg_optimizer_keeps_an_empty_group_with_an_id() -> None:
    root = _optimize('<g id="anchor"/><g fill="red"><rect display="none" width="1"/></g>')
    children = _children(root)
    assert [(_tag(c), c.get("id")) for c in children] == [("g", "anchor")]


def test_svg_optimizer_keeps_hidden_elements_anywhere_inside_a_reference() -> None:
    root = _optimize('<symbol id="s"><g fill="red"><rect display="none" width="1"/></g></symbol>')
    symbol = _children(root)[0]
    assert len(symbol) == 1
    assert _tag(symbol[0][0]) == "rect"


def test_svg_optimizer_unwraps_a_bare_group_in_place_and_keeps_its_tail() -> None:
    root = _optimize(
        '<g fill="red"><rect width="0"/><g><rect width="1"/><rect width="2"/></g>x'
        '<rect width="3"/></g>'
    )
    group = _children(root)[0]
    assert [r.get("width") for r in group] == ["0", "1", "2", "3"]
    assert [r.tail for r in group] == [None, None, "x", None]


def test_svg_optimizer_unwraps_nested_bare_groups_into_their_parent() -> None:
    root = _optimize(
        '<g><rect width="1"/><g><rect width="2"/><g><rect width="3"/></g></g></g><rect width="4"/>'
    )
    assert [(_tag(c), c.get("width")) for c in _children(root)] == [
        ("rect", "1"),
        ("rect", "2"),
        ("rect", "3"),
        ("rect", "4"),
    ]


def test_svg_optimizer_leaves_groups_apart_under_a_style_sheet() -> None:
    root = _optimize(
        "<style>.a { stroke: red }</style>"
        '<g fill="none" stroke="#000"><path d="M0 0L1.00000001 0"/></g>'
        '<g fill="none" stroke="#000"><path d="M0 1L1 1"/></g>'
    )
    tags = [_tag(c) for c in _children(root)]
    assert tags == ["style", "g", "g"]
    # Rounding still applies, since no style sheet selects by a number.
    assert _children(root)[1][0].get("d") == "M0 0L1 0"


def test_svg_optimizer_leaves_path_data_it_cannot_read_alone() -> None:
    paths = [
        "M L1 1",
        "M0 0L1 2 3",
        "M0 0X1 1",
        "M0 0 A1 1 0 2 0 3 3",
    ]
    root = _optimize("".join(f'<path fill="red" d="{d}"/>' for d in paths))
    assert [p.get("d") for p in _children(root)] == paths


def test_svg_optimizer_reads_closepath_repeated_arguments_and_outer_whitespace() -> None:
    root = _optimize('<path fill="red" d="  M0,0 L1.0000001 1 2 2zm3 3 h1 v1 Z "/>')
    assert _children(root)[0].get("d") == "M0 0L1 1 2 2zm3 3h1v1Z"
