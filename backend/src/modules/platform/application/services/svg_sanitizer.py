"""
Cleans an uploaded SVG so it can be stored and shown without running
anything. An SVG is XML that a browser treats as a document: it can carry
scripts, event handler attributes, links and HTML through foreignObject,
and any of those runs in Glados' origin once the file is opened directly.

The cleaner parses with defusedxml, which refuses entity expansion and
external entities, and keeps only an allowlist of drawing elements. A link
or anchor element is unwrapped, keeping the drawing inside it; any other
element outside the list is dropped with its content. On the elements that
stay it drops event handler attributes, every namespaced attribute except
`xlink:href` and `xml:space`, links that leave the document (only `#id`
references and embedded raster images stay), and `url()` references in
attributes and style sheets that point outside the document. Comments and
processing instructions are not kept. What comes out is a plain drawing.
"""

import re
from collections.abc import Iterable
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ALLOWED_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "symbol",
        "use",
        "title",
        "desc",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "textPath",
        "clipPath",
        "mask",
        "pattern",
        "marker",
        "linearGradient",
        "radialGradient",
        "stop",
        "style",
        "image",
    }
)

# Elements whose children are kept while the element itself goes.
UNWRAPPED_ELEMENTS = frozenset({"a", "switch"})

_HREF_ATTRIBUTES = frozenset({"href", f"{{{XLINK_NS}}}href"})
_KEPT_NAMESPACED = frozenset({f"{{{XLINK_NS}}}href", f"{{{XML_NS}}}space"})
_ATTRIBUTE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_RASTER_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=\s]+$")
_URL_FUNCTION = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
_CSS_IMPORT = re.compile(r"@import[^;]*;?", re.IGNORECASE)
_CSS_DANGEROUS = re.compile(r"expression\s*\(|javascript:|behavior\s*:|-moz-binding", re.IGNORECASE)


class SvgRejectedError(ValueError):
    """The upload is not an SVG drawing the cleaner can keep."""


def _local(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, _, local = tag[1:].partition("}")
        return namespace, local
    return None, tag


def _clean_urls(value: str) -> str:
    """Keeps `url(#id)` references and blanks every other `url()`."""

    def replace(match: re.Match[str]) -> str:
        target = match.group(2).strip()
        return match.group(0) if target.startswith("#") else "none"

    return _URL_FUNCTION.sub(replace, value)


def _clean_css(css: str) -> str:
    css = _CSS_IMPORT.sub("", css)
    css = _clean_urls(css)
    return _CSS_DANGEROUS.sub("", css)


def _href_allowed(element_local: str, value: str) -> bool:
    target = value.strip()
    if target.startswith("#"):
        return True
    return element_local == "image" and bool(_RASTER_DATA_URL.match(target))


def _clean_attributes(element: ET.Element, element_local: str) -> None:
    for name in list(element.attrib):
        value = element.attrib[name]
        namespace, local = _local(name)
        keep = True
        if (
            (namespace is not None and name not in _KEPT_NAMESPACED)
            or (namespace is None and not _ATTRIBUTE_NAME.match(local))
            or local.lower().startswith("on")
        ):
            keep = False
        elif name in _HREF_ATTRIBUTES:
            keep = _href_allowed(element_local, value)
        if not keep:
            del element.attrib[name]
            continue
        if local == "style":
            element.attrib[name] = _clean_css(value)
        elif "url(" in value.lower():
            element.attrib[name] = _clean_urls(value)


def _clean_children(element: ET.Element) -> None:
    """Cleans the children of `element` in place, unwrapping or dropping
    the ones outside the allowlist."""
    index = 0
    while index < len(element):
        child = element[index]
        if not isinstance(child.tag, str):
            # Comments and processing instructions.
            del element[index]
            continue
        namespace, local = _local(child.tag)
        if namespace == SVG_NS and local in UNWRAPPED_ELEMENTS:
            grandchildren: Iterable[ET.Element] = list(child)
            del element[index]
            for offset, grandchild in enumerate(grandchildren):
                element.insert(index + offset, grandchild)
            continue
        if namespace != SVG_NS or local not in ALLOWED_ELEMENTS:
            del element[index]
            continue
        _clean_attributes(child, local)
        if local == "style":
            child.text = _clean_css(child.text or "")
            for grandchild in list(child):
                child.remove(grandchild)
        else:
            _clean_children(child)
        index += 1


def sanitize_svg(data: bytes) -> bytes:
    """The cleaned drawing, UTF-8 encoded. Raises SvgRejectedError for
    anything that is not well-formed SVG or uses entities."""
    try:
        root = DefusedET.fromstring(data)
    except (DefusedXmlException, ET.ParseError) as exc:
        raise SvgRejectedError(f"The file is not a well-formed SVG: {exc}") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise SvgRejectedError("The file is not an SVG drawing.")

    _clean_attributes(root, "svg")
    _clean_children(root)

    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    cleaned: bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return cleaned
