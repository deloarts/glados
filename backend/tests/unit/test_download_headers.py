"""
Unit tests for build_download_headers, the hardening shared by every new
Item-3 download route (item-file downloads, admin backup downloads):
nosniff, CRLF-stripped/RFC-5987 Content-Disposition, and forced
attachment for anything outside the inline-safe allowlist regardless of
what the caller asked for.
"""

from src.modules.platform.adapters.inbound.api.download_headers import build_download_headers


def test_nosniff_is_always_present() -> None:
    headers = build_download_headers("f.pdf", content_type="application/pdf")
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_cache_control_matches_the_avatar_route() -> None:
    headers = build_download_headers("f.pdf", content_type="application/pdf")
    assert headers["Cache-Control"] == "private, max-age=3600"


def test_default_disposition_is_attachment() -> None:
    headers = build_download_headers("f.pdf", content_type="application/pdf")
    assert headers["Content-Disposition"].startswith("attachment;")


def test_inline_is_honoured_for_an_allowlisted_image_type() -> None:
    headers = build_download_headers("f.png", content_type="image/png", disposition="inline")
    assert headers["Content-Disposition"].startswith("inline;")


def test_inline_is_honoured_for_pdf() -> None:
    headers = build_download_headers("f.pdf", content_type="application/pdf", disposition="inline")
    assert headers["Content-Disposition"].startswith("inline;")


def test_html_is_forced_to_attachment_even_when_inline_is_requested() -> None:
    headers = build_download_headers("f.html", content_type="text/html", disposition="inline")
    assert headers["Content-Disposition"].startswith("attachment;")


def test_svg_is_forced_to_attachment_even_when_inline_is_requested() -> None:
    headers = build_download_headers("f.svg", content_type="image/svg+xml", disposition="inline")
    assert headers["Content-Disposition"].startswith("attachment;")


def test_an_unrecognized_type_is_forced_to_attachment_even_when_inline_is_requested() -> None:
    headers = build_download_headers(
        "f.step", content_type="application/octet-stream", disposition="inline"
    )
    assert headers["Content-Disposition"].startswith("attachment;")


def test_crlf_is_stripped_from_the_file_name() -> None:
    headers = build_download_headers("evil\r\nX-Injected: 1.pdf", content_type="application/pdf")
    disposition = headers["Content-Disposition"]
    assert "\r" not in disposition
    assert "\n" not in disposition
    assert "X-Injected" not in disposition or "evilX-Injected: 1.pdf" in disposition


def test_non_ascii_file_name_gets_both_plain_and_rfc5987_forms() -> None:
    headers = build_download_headers("Résumé.pdf", content_type="application/pdf")
    disposition = headers["Content-Disposition"]
    assert 'filename="R' in disposition
    assert "filename*=UTF-8''R%C3%A9sum%C3%A9.pdf" in disposition


def test_empty_file_name_falls_back_to_a_safe_default() -> None:
    headers = build_download_headers("\r\n", content_type="application/pdf")
    disposition = headers["Content-Disposition"]
    assert 'filename="download"' in disposition
