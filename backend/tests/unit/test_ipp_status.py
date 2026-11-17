"""
Unit tests for the pure IPP reply parsing in ipp_status.py. Byte fixtures
are hand-built with the same encoding print_document_printer_gateway uses
to build requests, so this exercises the real wire format without a socket.
"""

import struct

import pytest

from src.modules.quality.domain.services.ipp_status import describe_ipp_identity
from src.modules.quality.domain.services.ipp_status import describe_ipp_print_result
from src.modules.quality.domain.services.ipp_status import describe_ipp_status
from src.modules.quality.domain.services.ipp_status import ipp_attributes_substituted
from src.modules.quality.domain.services.ipp_status import parse_ipp_reply


def _attr(tag: int, name: str, value: bytes) -> bytes:
    return (
        bytes([tag])
        + struct.pack(">H", len(name))
        + name.encode()
        + struct.pack(">H", len(value))
        + value
    )


def _reply(status: int, group: bytes) -> bytes:
    header = b"\x02\x00" + struct.pack(">H", status) + struct.pack(">I", 1)
    return header + b"\x01" + group + b"\x03"


def test_parse_ipp_reply_extracts_status_and_attributes():
    group = _attr(0x45, "printer-make-and-model", b"KONICA MINOLTA bizhub C251i")
    reply = _reply(0x0000, group)

    status, attributes = parse_ipp_reply(reply)

    assert status == 0x0000
    assert ("printer-make-and-model", b"KONICA MINOLTA bizhub C251i") in attributes


def test_parse_ipp_reply_folds_set_valued_attributes_onto_preceding_name():
    group = _attr(0x44, "document-format-supported", b"application/pdf") + _attr(
        0x44, "", b"application/octet-stream"
    )
    reply = _reply(0x0000, group)

    _, attributes = parse_ipp_reply(reply)

    names = [name for name, _ in attributes]
    assert names.count("document-format-supported") == 2


def test_describe_ipp_identity_formats_wanted_attributes():
    group = _attr(0x45, "printer-make-and-model", b"KONICA MINOLTA bizhub C251i")
    status, attributes = parse_ipp_reply(_reply(0x0000, group))

    text = describe_ipp_identity(status, attributes)

    assert "ipp status: 0x0000" in text
    assert "KONICA MINOLTA bizhub C251i" in text


def test_describe_ipp_status_formats_state_attributes():
    group = _attr(0x44, "printer-state-message", b"Idle") + _attr(
        0x22, "printer-is-accepting-jobs", b"\x01"
    )
    status, attributes = parse_ipp_reply(_reply(0x0000, group))

    lines = describe_ipp_status(status, attributes)

    assert "ipp status: 0x0000" in lines[0]
    assert any("Idle" in line for line in lines)


def test_identity_and_status_describe_disjoint_attribute_sets():
    # status() must not just reuse identify()'s reply verbatim, or the
    # Printer Status dialog shows two identical boxes. A reply carrying one
    # attribute from each set must show up in only its own section.
    group = _attr(0x45, "printer-make-and-model", b"KONICA MINOLTA bizhub C251i") + _attr(
        0x44, "printer-state-message", b"Idle"
    )
    status, attributes = parse_ipp_reply(_reply(0x0000, group))

    identity = describe_ipp_identity(status, attributes)
    status_lines = describe_ipp_status(status, attributes)
    status_text = "\n".join(status_lines)

    assert "KONICA MINOLTA bizhub C251i" in identity
    assert "printer-state-message" not in identity

    assert "Idle" in status_text
    assert "printer-make-and-model" not in status_text


def test_describe_ipp_print_result_success():
    group = _attr(0x21, "job-id", struct.pack(">I", 42))
    status, attributes = parse_ipp_reply(_reply(0x0000, group))

    result = describe_ipp_print_result(status, attributes)

    assert "job-id 42 accepted" in result


def test_describe_ipp_print_result_error_status_raises():
    group = _attr(0x44, "status-message", b"client-error-not-found")
    status, attributes = parse_ipp_reply(_reply(0x0400, group))

    with pytest.raises(ValueError, match="client-error-not-found"):
        describe_ipp_print_result(status, attributes)


@pytest.mark.parametrize(
    ("status", "substituted"),
    [(0x0000, False), (0x0001, True), (0x0002, True), (0x0400, False)],
)
def test_ipp_attributes_substituted_only_for_ok_with_substitution(status, substituted):
    assert ipp_attributes_substituted(status) is substituted
