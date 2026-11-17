"""
Matching a name written in meeting notes to users and contacts: every word
must fit, a single letter as an initial, at least one word in full; titles
and what follows a comma or parenthesis are ignored, accents and case too;
an e-mail address matches on its own; a tie preselects nobody.
"""

from src.modules.workspace.domain.services.person_name_matching import PersonCandidate
from src.modules.workspace.domain.services.person_name_matching import PersonKind
from src.modules.workspace.domain.services.person_name_matching import match_person

HANS = PersonCandidate(kind=PersonKind.USER, id=1, name="Hans Müller", aliases=("hmueller",))
HANNA = PersonCandidate(kind=PersonKind.USER, id=2, name="Hanna Maier")
ERIKA = PersonCandidate(
    kind=PersonKind.CONTACT, id=7, name="Erika Blank", email="e.blank@example.com"
)
EVERYONE = [HANS, HANNA, ERIKA]


def test_a_full_name_matches_ignoring_accents_and_case() -> None:
    assert match_person("hans mueller", EVERYONE).best is None
    assert match_person("HANS MÜLLER", EVERYONE).best == HANS
    assert match_person("Hans Muller", EVERYONE).best == HANS


def test_a_first_name_with_an_initial_matches() -> None:
    assert match_person("Hans M.", EVERYONE).best == HANS


def test_titles_and_the_company_after_the_name_are_ignored() -> None:
    assert match_person("Hr. Müller (Lieferant GmbH)", EVERYONE).best == HANS
    assert match_person("Frau Blank, Fa. Kunde", EVERYONE).best == ERIKA


def test_a_word_that_fits_nobody_matches_nobody() -> None:
    match = match_person("Hans Hypothetical", EVERYONE)
    assert match.best is None and match.candidates == []


def test_initials_alone_match_nobody() -> None:
    assert match_person("H. M.", EVERYONE).candidates == []


def test_an_email_address_matches_on_its_own() -> None:
    assert match_person("E. B. <e.blank@example.com>", EVERYONE).best == ERIKA


def test_a_username_matches_on_its_own() -> None:
    assert match_person("hmueller", EVERYONE).best == HANS


def test_a_tie_offers_both_and_preselects_nobody() -> None:
    twin = PersonCandidate(kind=PersonKind.CONTACT, id=9, name="Hans Müller")
    match = match_person("Hans", [HANS, twin, HANNA])
    assert match.best is None
    assert {c.id for c in match.candidates} == {1, 9}
