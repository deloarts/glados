"""
The meeting notes mail template ships as a body fragment in both languages:
its `<title>` carries the subject, which an import lifts out of the body the
compose dialog starts from, and both texts end with the acceptance clause.
"""

from pathlib import Path

from src.modules.platform.adapters.outbound.external.mail import render as mail_render
from src.modules.platform.adapters.outbound.external.mail.render import packaged_title
from src.modules.platform.domain.services.mail_template_specs import MAIL_TEMPLATE_SPECS
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind

_TEMPLATES = Path(mail_render.__file__).parent / "templates"


def _body(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def test_the_fragments_carry_the_subject_in_their_title():
    assert packaged_title("meeting_notes.enGB.html") == (
        "Minutes {{ meeting_number }}: {{ meeting_name }}"
    )
    assert packaged_title("meeting_notes.deAT.html") == (
        "Protokoll {{ meeting_number }}: {{ meeting_name }}"
    )


def test_the_fragments_use_their_variables_and_end_with_the_acceptance_clause():
    english = _body("meeting_notes.enGB.html")
    german = _body("meeting_notes.deAT.html")
    for body in (english, german):
        assert "<html" not in body
        assert "{{ issue }}" in body and "{{ user_full_name }}" in body
    assert english.rstrip().endswith(
        "<p>These minutes count as accepted unless you object within 7 days.</p>"
    )
    assert german.rstrip().endswith(
        "<p>Dieses Protokoll gilt als angenommen, wenn Du nicht innerhalb von 7 Tagen "
        "widersprichst.</p>"
    )


def test_a_whole_document_keeps_its_title():
    assert "<title>" in _body("welcome.enGB.html")


def test_the_spec_declares_the_variables_the_fragments_use():
    spec = MAIL_TEMPLATE_SPECS[MailTemplateKind.MEETING_NOTES]

    assert set(spec.variables) == {
        "meeting_name",
        "meeting_number",
        "meeting_date",
        "owner_number",
        "issue",
        "user_full_name",
        "user_email",
    }
