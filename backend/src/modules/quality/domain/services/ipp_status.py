"""
Pure parsing of an IPP `Get-Printer-Attributes` reply. No sockets, no
network, the round trip lives in the printer gateway adapter; this stays
unit-testable with no printer present.
"""

import struct

# Fixed capabilities: what the printer IS, not what it's doing right now.
_IDENTITY_ATTRIBUTES = (
    "printer-make-and-model",
    "document-format-supported",
    "media-supported",
    "media-default",
)

# Moment-to-moment state: paused, out of media, rejecting jobs. The IPP
# counterpart of ZPL's ~HS (describe_zpl_status): both come from a single
# Get-Printer-Attributes reply, unlike ZPL where ~HI/~HS are two distinct
# queries, but the same reply carries both identity and status attributes,
# so the two describe_* functions each pick their own subset out of it.
_STATUS_ATTRIBUTES = (
    "printer-state-message",
    "printer-state-reasons",
    "printer-is-accepting-jobs",
)


def parse_ipp_reply(reply: bytes) -> tuple[int, list[tuple[str, bytes]]]:
    """Return the status code and a flat list of (name, raw value) attributes.

    Additional values of a set-valued attribute arrive with an empty name;
    they are folded onto the preceding attribute's name so callers can just
    filter by name.
    """
    status = struct.unpack(">H", reply[2:4])[0]
    offset, attributes, last_name = 9, [], ""

    while offset < len(reply):
        tag = reply[offset]
        offset += 1
        if tag in (0x02, 0x03, 0x04, 0x05):  # group delimiters / end
            if tag == 0x03:
                break
            continue

        (name_length,) = struct.unpack(">H", reply[offset : offset + 2])
        offset += 2
        name = reply[offset : offset + name_length].decode("utf-8", "replace")
        offset += name_length
        (value_length,) = struct.unpack(">H", reply[offset : offset + 2])
        offset += 2
        value = reply[offset : offset + value_length]
        offset += value_length

        attributes.append((name or last_name, value))
        last_name = name or last_name

    return status, attributes


def _describe(status: int, attributes: list[tuple[str, bytes]], keys: tuple[str, ...]) -> list[str]:
    lines = [f"ipp status: 0x{status:04x}"]
    for key in keys:
        values = [
            value.decode("utf-8", "replace") for name, value in attributes if name == key and value
        ]
        if values:
            lines.append(f"{key + ':':<28}{', '.join(values)}")
    return lines


def describe_ipp_identity(status: int, attributes: list[tuple[str, bytes]]) -> str:
    """Format a Get-Printer-Attributes reply's fixed-capability fields."""
    return "\n".join(_describe(status, attributes, _IDENTITY_ATTRIBUTES))


def describe_ipp_status(status: int, attributes: list[tuple[str, bytes]]) -> list[str]:
    """Format a Get-Printer-Attributes reply's moment-to-moment state fields."""
    return _describe(status, attributes, _STATUS_ATTRIBUTES)


def describe_ipp_print_result(status: int, attributes: list[tuple[str, bytes]]) -> str:
    """Format a Print-Job reply. Raises ValueError for any non-success status."""
    details = dict(attributes)
    job_id = struct.unpack(">I", details["job-id"])[0] if "job-id" in details else "?"
    message = details.get("status-message", b"").decode("utf-8", "replace")

    if status >= 0x0100:  # anything above successful-ok-* is an error
        raise ValueError(f"printer rejected the job: 0x{status:04x} {message}".strip())

    return f"job-id {job_id} accepted (ipp status 0x{status:04x}{' ' + message if message else ''})"


def ipp_attributes_substituted(status: int) -> bool:
    """Whether a successful Print-Job reply says the printer accepted the job
    but did not honour every requested attribute: successful-ok-ignored-or-
    substituted-attributes (0x0001) or successful-ok-conflicting-attributes
    (0x0002). A printer without a duplex unit answers this way when asked to
    print both sides, and prints one-sided instead."""
    return status in (0x0001, 0x0002)
