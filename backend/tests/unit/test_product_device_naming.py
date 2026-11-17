import pytest

from src.modules.workspace.domain.errors import ProductDeviceNameInvalidError
from src.modules.workspace.domain.policies.product_device_naming import clean_part
from src.modules.workspace.domain.policies.product_device_naming import compose_device_name
from src.modules.workspace.domain.policies.product_device_naming import group_key
from src.modules.workspace.domain.policies.product_device_naming import invalid_characters
from src.modules.workspace.domain.policies.product_device_naming import to_ascii
from src.modules.workspace.domain.policies.product_device_naming import with_product_number


def test_product_device_naming_composes_utf8_and_ascii() -> None:
    name = compose_device_name("B01-W4-L", "Hubzylinder Einförderung", "P", 1)
    assert name.utf8 == "B01-W4-L Hubzylinder Einförderung P1"
    assert name.ascii == "B01_W4_L_Hubzylinder_Einfoerderung_P1"
    assert name.ascii_key == "b01_w4_l_hubzylinder_einfoerderung_p1"


def test_product_device_naming_without_location() -> None:
    name = compose_device_name("", "Greifer", "HP", 3)
    assert name.utf8 == "Greifer HP3"
    assert name.ascii == "Greifer_HP3"


def test_product_device_naming_transliterates_umlauts_and_accents() -> None:
    assert to_ascii("Größe Äußere Öse Überlauf") == "Groesse_Aeussere_Oese_Ueberlauf"
    assert to_ascii("Café  Crème") == "Cafe_Creme"


def test_product_device_naming_turns_every_other_character_into_one_underscore() -> None:
    assert to_ascii("B01-B Zylinder 1+2, Spann.-Einheit (alt) & neu") == (
        "B01_B_Zylinder_1_2_Spann_Einheit_alt_neu"
    )
    assert to_ascii("-Rand_ _Zylinder-") == "Rand_Zylinder"
    assert compose_device_name("-", "Greifer", "P", 1).ascii == "Greifer_P1"


def test_product_device_naming_clean_part_needs_a_letter_or_digit() -> None:
    with pytest.raises(ProductDeviceNameInvalidError):
        clean_part("- + -", "name", required=True, max_length=50)


def test_product_device_naming_prefixes_product_number() -> None:
    full = with_product_number("M26001", compose_device_name("B01", "Push Cylinder", "P", 1))
    assert full.utf8 == "M26001 B01 Push Cylinder P1"
    assert full.ascii == "M26001_B01_Push_Cylinder_P1"


def test_product_device_naming_reports_file_name_illegal_and_non_ascii_characters() -> None:
    assert invalid_characters('a/b:c*d?e"f<g>h|i\\') == list('/:*?"<>|\\')
    assert invalid_characters("Ventil ø 20") == ["ø"]
    assert invalid_characters("Hubzylinder Einförderung") == []


def test_product_device_naming_clean_part_collapses_whitespace() -> None:
    assert clean_part("  Hub   zylinder ", "name", required=True, max_length=50) == "Hub zylinder"


def test_product_device_naming_clean_part_rejects_empty_required_name() -> None:
    with pytest.raises(ProductDeviceNameInvalidError):
        clean_part("   ", "name", required=True, max_length=50)


def test_product_device_naming_clean_part_rejects_illegal_characters() -> None:
    with pytest.raises(ProductDeviceNameInvalidError):
        clean_part("Zylinder 1/2", "name", required=True, max_length=50)


def test_product_device_naming_group_key_treats_transliterations_alike() -> None:
    assert group_key("B01", "Einförderung", "P") == group_key("b01", "Einfoerderung", "P")
    assert group_key("B01", "Einförderung", "P") != group_key("B01", "Einförderung", "H")


def test_product_device_naming_without_letter_numbers_from_the_second_device() -> None:
    first = compose_device_name("", "Taster Start", "", 1)
    second = compose_device_name("", "Taster Start", "", 2)
    assert (first.utf8, first.ascii) == ("Taster Start", "Taster_Start")
    assert (second.utf8, second.ascii) == ("Taster Start 2", "Taster_Start_2")
