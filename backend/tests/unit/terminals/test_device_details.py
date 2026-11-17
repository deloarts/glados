"""The device details a terminal reports: cleaned rather than refused, text
cut to its cap, implausible numbers dropped, and the identifying fields left
out for readers without manage:terminals."""

from src.modules.operations.domain.value_objects.terminal_device_details import HOSTNAME_MAX
from src.modules.operations.domain.value_objects.terminal_device_details import SHORT_TEXT_MAX
from src.modules.operations.domain.value_objects.terminal_device_details import TEXT_MAX
from src.modules.operations.domain.value_objects.terminal_device_details import (
    device_details_to_data,
)
from src.modules.operations.domain.value_objects.terminal_device_details import parse_device_details


def test_device_details_keep_a_plausible_report() -> None:
    raw = {
        "computer_model": "Raspberry Pi 4 Model B Rev 1.5",
        "computer_serial": "10000000abcdef01",
        "ram_mb": 3790,
        "cpu_temperature_c": 50.123,
        "uptime_seconds": 86400,
        "kernel": "6.18.50+rpt-rpi-v8",
        "os_name": "Debian GNU/Linux 13 (trixie)",
        "hostname": "IND-SBC-0001",
        "under_voltage": False,
        "display_make": "SAM",
        "display_model": "S27D390",
        "display_serial": "H4ZH800000",
        "display_width_px": 1920,
        "display_height_px": 1080,
        "display_width_mm": 600,
        "display_height_mm": 340,
        "display_connector": "HDMI-A-1",
        "display_connected": True,
        "display_power_state": "On",
        "cec_available": True,
    }
    details = parse_device_details(raw)
    data = device_details_to_data(details)
    assert data == {**raw, "cpu_temperature_c": 50.1, "throttled": None}


def test_device_details_cut_text_and_drop_control_characters() -> None:
    details = parse_device_details(
        {
            "computer_model": "Pi\x00 4\n" + "x" * 500,
            "hostname": "h" * 400,
            "display_serial": "s" * 100,
            "kernel": "   ",
        }
    )
    assert details.computer_model is not None
    assert details.computer_model.startswith("Pi 4 x")
    assert len(details.computer_model) == TEXT_MAX
    assert details.hostname == "h" * HOSTNAME_MAX
    assert details.display_serial == "s" * SHORT_TEXT_MAX
    assert details.kernel is None


def test_device_details_drop_implausible_or_mistyped_values() -> None:
    details = parse_device_details(
        {
            "ram_mb": -1,
            "cpu_temperature_c": float("nan"),
            "uptime_seconds": 1.5,
            "display_width_px": True,
            "display_height_px": "1080",
            "display_connected": "yes",
            "computer_model": 42,
            "unknown_field": "ignored",
        }
    )
    assert device_details_to_data(details) == dict.fromkeys(device_details_to_data(details))


def test_device_details_without_identifiers_hides_serials_and_hostname() -> None:
    details = parse_device_details(
        {
            "computer_model": "Pi",
            "computer_serial": "1",
            "display_serial": "2",
            "hostname": "kiosk",
        }
    )
    hidden = details.without_identifiers()
    assert (hidden.computer_serial, hidden.display_serial, hidden.hostname) == (None, None, None)
    assert hidden.computer_model == "Pi"
