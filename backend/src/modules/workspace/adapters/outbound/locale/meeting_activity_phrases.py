"""
Reads the words of the bundled meeting notification from the locale data
files next to this module, meeting_activity.<language>.json, one per
shipped language. They are the backend's locale files for these texts, so
the code stays in English and a language is added by adding its file.
"""

import json
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from src.modules.platform.domain.value_objects.language import Language
from src.modules.workspace.domain.value_objects.meeting_activity_phrases import (
    MeetingActivityPhrases,
)
from src.modules.workspace.domain.value_objects.meeting_activity_phrases import (
    MeetingActivitySentences,
)

_DIR = Path(__file__).parent


def _sentences(data: dict[str, Any]) -> MeetingActivitySentences:
    return MeetingActivitySentences(
        mentions_and_todos=data["mentions_and_todos"],
        mentions=data["mentions"],
        todos=data["todos"],
    )


def _phrases(language: Language) -> MeetingActivityPhrases:
    path = _DIR / f"meeting_activity.{language.value}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return MeetingActivityPhrases(
        title=data["title"],
        someone=data["someone"],
        list_separator=data["list_separator"],
        last_separator=data["last_separator"],
        once=data["once"],
        twice=data["twice"],
        times=data["times"],
        one_todo=data["one_todo"],
        todos=data["todos"],
        one_actor=_sentences(data["one_actor"]),
        several_actors=_sentences(data["several_actors"]),
    )


@cache
def meeting_activity_phrases() -> MappingProxyType[Language, MeetingActivityPhrases]:
    """The phrases of every shipped language, read once per process."""
    return MappingProxyType({language: _phrases(language) for language in Language})
