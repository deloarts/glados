"""
Unit tests for the pure ~HI/~HS parsing in zpl_status.py. Fixtures are the
actual replies captured from the ZT230 during prototyping, so this locks
in the real wire format, not an idealized one.
"""

from src.modules.quality.domain.services.zpl_status import describe_zpl_identity
from src.modules.quality.domain.services.zpl_status import describe_zpl_status

_HI_REPLY = "\x02ZT230-300dpi,V72.20.01Z,12,4096KB\x03"
_HS_REPLY = (
    "\x02030,0,0,0512,000,0,0,0,000,0,0,0\x03\r\n"
    "\x02128,0,0,1,0,2,5,0,00000000,1,000\x03\r\n"
    "\x021234,0\x03"
)


def test_describe_zpl_identity_strips_control_bytes():
    assert describe_zpl_identity(_HI_REPLY) == "ZT230-300dpi,V72.20.01Z,12,4096KB"


def test_describe_zpl_status_decodes_paper_and_pause_state():
    lines = describe_zpl_status(_HS_REPLY, head_dpi=300)
    assert "paper out:      no" in lines
    assert "paused:         no" in lines


def test_describe_zpl_status_converts_label_length_to_mm():
    lines = describe_zpl_status(_HS_REPLY, head_dpi=300)
    (label_length_line,) = [line for line in lines if line.startswith("label length:")]
    assert "512 dots" in label_length_line
    assert "43.3 mm" in label_length_line


def test_describe_zpl_status_flags_ribbon_out_and_direct_thermal():
    lines = describe_zpl_status(_HS_REPLY, head_dpi=300)
    assert "ribbon out:     YES" in lines
    assert "media type:     direct thermal" in lines


def test_describe_zpl_status_unexpected_reply_does_not_raise():
    lines = describe_zpl_status("garbage")
    assert len(lines) == 1
    assert "unexpected" in lines[0]


def test_an_unexpected_status_reply_is_not_echoed():
    lines = describe_zpl_status("SSH-2.0-OpenSSH_9.6 secret banner")
    assert "OpenSSH" not in lines[0]


def test_an_identity_reply_that_is_not_a_printers_is_not_echoed():
    assert "secret" not in describe_zpl_identity("HTTP/1.1 200 OK\r\nsecret: value\r\n\r\n")


def test_a_two_line_reply_that_is_not_zpl_is_not_echoed_and_does_not_raise():
    lines = describe_zpl_status("HTTP/1.1 400 Bad Request\r\nServer: something\r\n")

    assert lines == ["unexpected ~HS reply (45 characters), not a ZPL printer?"]


def test_a_reply_with_a_non_numeric_count_is_not_echoed():
    reply = "030,0,0,abc,000,0,0\r\n128,0,0,1,0,2,5,0,xyz,1,000\r\n"

    assert describe_zpl_status(reply) == [
        f"unexpected ~HS reply ({len(reply)} characters), not a ZPL printer?"
    ]


def test_an_unknown_print_mode_is_not_echoed():
    reply = _HS_REPLY.replace("128,0,0,1,0,2,", "128,0,0,1,0,<script>,")

    assert "print mode:     unknown" in describe_zpl_status(reply)
