"""
Turns the Data Portal's JSON:API documents into the domain's EdpPart and
EdpNumberMatch. A part's relationships point into the document's `included`
list: the manufacturer (short_name is the Data Portal code), the product
top, middle and sub group (catalogue entries with a name), the external
documents (type "1" is a web link, "0" a file path inside the portal) and
the picture file, whose preview holds the picture URL per size. Missing or
oddly typed pieces are skipped rather than failing the whole part, since
the portal's data is curated by many manufacturers.
"""

from dataclasses import replace
from typing import Any

from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpNumberMatch
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart

PART_INCLUDES = (
    "manufacturer,external_documents,picture_file.preview,"
    "product_top_group,product_group,product_sub_group"
)
PICTURE_SIZE = "512"
_GROUP_RELATIONS = ("product_top_group", "product_group", "product_sub_group")
_WEB_LINK_TYPE = "1"


def _str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _texts(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {k: v.strip() for k, v in value.items() if isinstance(k, str) and _str(v)}


def _index(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    included = document.get("included")
    if not isinstance(included, list):
        return {}
    return {
        (str(item.get("type")), str(item.get("id"))): item
        for item in included
        if isinstance(item, dict)
    }


def _related(
    resource: dict[str, Any], name: str, index: dict[tuple[str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    relationships = resource.get("relationships")
    if not isinstance(relationships, dict):
        return []
    data = (relationships.get(name) or {}).get("data")
    refs = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    return [
        index[(str(ref.get("type")), str(ref.get("id")))]
        for ref in refs
        if (str(ref.get("type")), str(ref.get("id"))) in index
    ]


def _attributes(resource: dict[str, Any]) -> dict[str, Any]:
    attributes = resource.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def parse_ean(identcode: Any) -> str | None:
    """The EAN of an identcode such as "4011209780774 EAN", None for any
    other kind of identcode."""
    text = _str(identcode)
    if not text:
        return None
    parts = text.split()
    if len(parts) == 2 and parts[1].upper() == "EAN" and parts[0].isdigit():
        return parts[0]
    return None


def part_page_url(site_url: str, part: EdpPart) -> str:
    supplier = part.part_number.split(".", 1)[0]
    return f"{site_url}/part-details/{supplier}/{part.part_number}/id-{part.part_id}"


def parse_part(
    resource: dict[str, Any], index: dict[tuple[str, str], dict[str, Any]], site_url: str
) -> EdpPart | None:
    raw_id = resource.get("id")
    if not str(raw_id).isdigit():
        return None
    part_id = int(str(raw_id))
    attributes = _attributes(resource)
    part_number = _str(attributes.get("part_number"))
    if not part_number:
        return None

    manufacturers = _related(resource, "manufacturer", index)
    manufacturer = _attributes(manufacturers[0]) if manufacturers else {}
    groups = tuple(
        name
        for relation in _GROUP_RELATIONS
        for entry in _related(resource, relation, index)
        if (name := _str(_attributes(entry).get("name")))
    )
    support_url = next(
        (
            url
            for doc in _related(resource, "external_documents", index)
            if str(_attributes(doc).get("external_document_type")) == _WEB_LINK_TYPE
            and (url := _str(_attributes(doc).get("external_document_value")))
            and url.lower().startswith(("https://", "http://"))
        ),
        None,
    )
    picture_url = next(
        (
            url
            for picture in _related(resource, "picture_file", index)
            for preview in _related(picture, "preview", index)
            if (url := _str(_attributes(preview).get(PICTURE_SIZE)))
        ),
        None,
    )
    part = EdpPart(
        part_id=part_id,
        part_number=part_number,
        order_number=_str(attributes.get("order_number")),
        type_number=_str(attributes.get("type_number")),
        designation=_texts(attributes.get("designation")),
        description=_texts(attributes.get("description")),
        ean=parse_ean(attributes.get("identcode")),
        manufacturer_code=_str(manufacturer.get("short_name")),
        manufacturer_name=_str(manufacturer.get("long_name")),
        product_groups=groups,
        support_url=support_url,
        picture_url=picture_url,
    )
    return replace(part, part_page_url=part_page_url(site_url, part))


def parse_parts(document: dict[str, Any], site_url: str) -> list[EdpPart]:
    data = document.get("data")
    resources = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    index = _index(document)
    parts = (parse_part(r, index, site_url) for r in resources if isinstance(r, dict))
    return [p for p in parts if p is not None]


def parse_number_matches(document: dict[str, Any], numbers: list[str]) -> list[EdpNumberMatch]:
    """One match per searched number, in the order searched. A number the
    portal answers several results for keeps them all."""
    data = document.get("data")
    results = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    found: dict[str, list[int]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        attributes = _attributes(result)
        search = attributes.get("search")
        part_id = attributes.get("partid")
        if not isinstance(search, str):
            continue
        ids = found.setdefault(search.strip(), [])
        if isinstance(part_id, int) and part_id not in ids:
            ids.append(part_id)
    return [EdpNumberMatch(search=n, part_ids=tuple(found.get(n.strip(), []))) for n in numbers]
