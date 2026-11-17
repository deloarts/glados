from datetime import UTC
from datetime import datetime

from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindSignal
from src.modules.workspace.domain.services.plc_naming import build_tags
from src.modules.workspace.domain.services.plc_naming import convert
from src.modules.workspace.domain.services.plc_naming import longest_tag_length
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_CONVERSIONS
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_EXPORT_COLUMNS
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_PREFIXES
from src.modules.workspace.domain.value_objects.plc_environment_settings import CharConversion
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

NOW = datetime(2026, 10, 24, tzinfo=UTC)


def _environment(max_length: int = 128) -> PlcEnvironment:
    return PlcEnvironment(
        id=1,
        created=NOW,
        changed=NOW,
        changes=[],
        name="TIA",
        is_default=True,
        prefixes=dict(TIA_PREFIXES),
        max_tag_length=max_length,
        conversions=list(TIA_CONVERSIONS),
        tag_table="Standard-Variablentabelle",
        safety_tag_table="Safety",
        export_sheet="PLC Tags",
        export_columns=list(TIA_EXPORT_COLUMNS),
    )


def _kind() -> ProductDeviceKind:
    def position(id: int, state: str, command: str) -> ProductDeviceKindPosition:
        return ProductDeviceKindPosition(
            id=id,
            kind_id=1,
            label=LocalizedText.of({"enGB": state}),
            takes_value=False,
            unit=None,
            sort_order=id,
            plc_state_name=state,
            plc_command_name=command,
        )

    return ProductDeviceKind(
        id=1,
        created=NOW,
        changed=NOW,
        changes=[],
        label=LocalizedText.of({"enGB": "Cylinder"}),
        sort_order=0,
        creator_id=1,
        positions=[position(10, "EIN", "Einfahren"), position(11, "AUS", "Ausfahren")],
    )


def _device(id: int, name: str, signals: list[ProductDeviceSignal]) -> ProductDevice:
    return ProductDevice(
        id=id,
        created=NOW,
        changed=NOW,
        changes=[],
        product_id=1,
        location="B01-B",
        name=name,
        driving_medium_id=1,
        number=1,
        name_utf8=f"B01-B {name} P1",
        name_ascii="",
        name_ascii_key="",
        group_key="",
        kind_id=1,
        creator_id=1,
        components=[
            ProductDeviceComponent(
                id=id * 10, device_id=id, product_id=1, role_id=1, sort_order=0, signals=signals
            )
        ],
    )


DI = ProductDeviceSignalType.DI
DO = ProductDeviceSignalType.DO


def test_convert_applies_the_table_then_cleans_up() -> None:
    assert convert("B01-B Spannzylinder Einförderung P1", list(TIA_CONVERSIONS)) == (
        "B01_B_Spannzylinder_Einfoerderung_P1"
    )
    longest_first = [CharConversion("e", "x"), CharConversion("ee", "E")]
    assert convert("Seehöhe", longest_first) == "SEhohx"


def test_build_tags_names_inputs_outputs_and_safety_signals() -> None:
    device = _device(
        1,
        "Spannzylinder",
        [
            ProductDeviceSignal(DI, "ausgefahren", confirms_position_id=11),
            ProductDeviceSignal(
                DO, "ausfahren", drives_position_id=11, safety=True, address="Q24.0"
            ),
            ProductDeviceSignal(DI, "Druck ok"),
            ProductDeviceSignal(DO, "x", tag_suffix="Sonder"),
            ProductDeviceSignal(DI, "y", tag_name="diFreierName"),
        ],
    )
    tags = build_tags([device], {1: _kind()}, _environment())
    assert [t.name for t in tags] == [
        "di_B01_B_Spannzylinder_P1_AUS",
        "fdq_B01_B_Spannzylinder_P1_Ausfahren",
        "di_B01_B_Spannzylinder_P1_Druck_ok",
        "dq_B01_B_Spannzylinder_P1_Sonder",
        "diFreierName",
    ]
    assert tags[1].tag_table == "Safety"
    assert tags[1].address == "Q24.0"
    assert tags[0].comment == "B01-B Spannzylinder P1: ausgefahren"
    assert [t.overridden for t in tags] == [False, False, False, True, True]


def test_build_tags_flags_long_and_duplicate_tags() -> None:
    signal = ProductDeviceSignal(DI, "ausgefahren", confirms_position_id=11)
    first = _device(1, "Zylinder", [signal])
    second = _device(2, "Zylinder", [signal])
    tags = build_tags([first, second], {1: _kind()}, _environment(max_length=20))
    assert all(t.duplicate for t in tags)
    assert all(t.too_long for t in tags)


def test_build_tags_ends_a_kind_signal_with_its_plc_name_and_describes_it_by_its_label() -> None:
    kind = _kind()
    kind.signals = [
        ProductDeviceKindSignal(
            id=30,
            kind_id=1,
            label=LocalizedText.of({"deAT": "Störung", "enGB": "Fault"}),
            signal_type=DI,
            plc_name="Stoerung",
            sort_order=0,
        )
    ]
    device = _device(
        1,
        "Achse",
        [
            ProductDeviceSignal(DI, "", kind_signal_id=30),
            ProductDeviceSignal(DI, "", confirms_position_id=11),
            ProductDeviceSignal(DI, "Störung Antrieb", kind_signal_id=30, tag_suffix="Fehler"),
        ],
    )
    tags = build_tags([device], {1: kind}, _environment(), language="deAT")
    assert [t.name for t in tags] == [
        "di_B01_B_Achse_P1_Stoerung",
        "di_B01_B_Achse_P1_AUS",
        "di_B01_B_Achse_P1_Fehler",
    ]
    # Without a meaning of its own a signal is described by what it picks.
    assert [t.comment for t in tags] == [
        "B01-B Achse P1: Störung",
        "B01-B Achse P1: AUS",
        "B01-B Achse P1: Störung Antrieb",
    ]


def test_longest_tag_length_counts_prefix_name_and_longest_position_name() -> None:
    # "fdi_" (4) + "B01_B_Zylinder_P1" (17) + "_" + "Einfahren" (9)
    assert longest_tag_length("B01-B Zylinder P1", _kind(), _environment()) == 31
