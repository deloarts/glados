import pytest

from src.modules.platform.domain.exceptions import LocalizedTextInvalidError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.localized_text import require_language


def test_localized_text_trims_and_drops_empty_values() -> None:
    text = LocalizedText.of({"enGB": "  Extended ", "deAT": "   "})
    assert text.as_dict() == {"enGB": "Extended"}


def test_localized_text_rejects_unknown_language() -> None:
    with pytest.raises(LocalizedTextInvalidError):
        LocalizedText.of({"frFR": "Sorti"})


def test_localized_text_resolves_requested_then_default_then_any() -> None:
    both = LocalizedText.of({"enGB": "Extended", "deAT": "Ausgefahren"})
    assert both.resolve("deAT", "enGB") == "Ausgefahren"

    english = LocalizedText.of({"enGB": "Extended"})
    assert english.resolve("deAT", "enGB") == "Extended"

    german = LocalizedText.of({"deAT": "Ausgefahren"})
    assert german.resolve("enGB", "enGB") == "Ausgefahren"

    assert LocalizedText.of({}).resolve("enGB", "enGB") == ""


def test_localized_text_require_language_rejects_missing_default() -> None:
    with pytest.raises(LocalizedTextInvalidError):
        require_language(LocalizedText.of({"enGB": "Open"}), "deAT", "label")


def test_localized_text_require_language_accepts_present_default() -> None:
    text = LocalizedText.of({"deAT": "Offen"})
    # Must not raise: the default language is present.
    require_language(text, "deAT", "label")
    assert text.has("deAT")
