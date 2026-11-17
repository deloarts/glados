"""tests/unit/eplan_data_portal/test_parsing.py: JSON:API documents to EdpPart."""

from src.modules.external_data.adapters.outbound.external.eplan_data_portal.parsing import parse_ean
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.parsing import (
    parse_number_matches,
)
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.parsing import (
    parse_parts,
)
from tests.unit.eplan_data_portal._documents import PICTURE_URL
from tests.unit.eplan_data_portal._documents import check_document
from tests.unit.eplan_data_portal._documents import parts_document

SITE = "https://portal.example.test"


def test_edp_parse_part_resolves_every_included_relation() -> None:
    [part] = parse_parts(parts_document(), SITE)

    assert part.part_id == 451627
    assert part.order_number == "3RT2015-1BB41"
    assert part.ean == "4011209780774"
    assert (part.manufacturer_code, part.manufacturer_name) == ("SIE", "Siemens")
    assert part.product_groups == ("Electrical engineering", "Relays, contactors", "Contactors")
    assert part.product_family_name == "Contactors"
    assert part.support_url == "https://support.example.test/3RT2015"
    assert part.picture_url == PICTURE_URL
    assert part.part_page_url == f"{SITE}/part-details/SIE/SIE.3RT2015-1BB41/id-451627"


def test_edp_part_text_falls_back_across_languages_and_to_the_description() -> None:
    [part] = parse_parts(parts_document(), SITE)

    assert part.text_in("de_DE") == "SCHUETZ 3KW"
    assert part.text_in("en_US") == "CONTACTOR 3KW"
    empty = type(part)(
        part_id=1,
        part_number="X.1",
        order_number=None,
        type_number=None,
        description={"en_US": "Only a description"},
    )
    assert empty.text_in("de_DE") == "Only a description"


def test_edp_parse_skips_resources_without_id_or_part_number() -> None:
    document = parts_document()
    document["data"].append({"type": "parts", "id": "abc", "attributes": {"part_number": "X"}})
    document["data"].append({"type": "parts", "id": "5", "attributes": {}})

    assert [p.part_id for p in parse_parts(document, SITE)] == [451627]


def test_edp_parse_ean_accepts_only_ean_identcodes() -> None:
    assert parse_ean("4011209780774 EAN") == "4011209780774"
    assert parse_ean("4011209780774 UPC") is None
    assert parse_ean(None) is None


def test_edp_number_matches_keep_the_order_searched_and_every_hit() -> None:
    matches = parse_number_matches(check_document(), ["1234", "3RT2015-1BB41", "6ES7", "none"])

    assert [(m.search, m.part_ids) for m in matches] == [
        ("1234", (1, 2)),
        ("3RT2015-1BB41", (451627,)),
        ("6ES7", ()),
        ("none", ()),
    ]
