"""
The per-language name uniqueness of the labeled catalogue entities: a name
clashes only with another live row's name in the same language, ignoring
case and surrounding whitespace, and never with the row being saved.
"""

from src.modules.catalogue.domain.services.label_name_rules import NameClash
from src.modules.catalogue.domain.services.label_name_rules import find_name_clash
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


def _text(**values: str) -> LocalizedText:
    return LocalizedText(values=values)


def test_same_text_in_the_same_language_clashes() -> None:
    others = [(7, _text(enGB="Screws", deAT="Screws (deAT)"))]
    clash = find_name_clash(0, _text(enGB=" screws "), others)
    assert clash == NameClash(language="enGB", text=" screws ", other_id=7)


def test_same_text_in_another_language_does_not_clash() -> None:
    others = [(7, _text(enGB="Screws"))]
    assert find_name_clash(0, _text(deAT="Screws"), others) is None


def test_the_row_being_saved_is_skipped() -> None:
    others = [(7, _text(enGB="Screws"))]
    assert find_name_clash(7, _text(enGB="Screws"), others) is None
