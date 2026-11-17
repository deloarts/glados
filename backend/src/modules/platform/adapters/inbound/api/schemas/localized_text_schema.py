"""
Wire shapes of a localized label. A request carries an object from language
code (`enGB`, `deAT`) to text; only its size is bounded here, while unknown
language codes and the default-language requirement are domain rules
(`LocalizedText.of`, `require_language`), so every surface rejects them the
same way. `LocalizedLongTextIn` is the same shape for longer texts such as
descriptions.

`ResolvedLabel` is the other direction, for a surface that answers with one
string per label: it accepts the stored language map and keeps the text in
the request's label languages (see `infrastructure/label_languages.py`), falling back to
the first language that has one.
"""

from typing import Annotated
from typing import Any

from pydantic import BeforeValidator
from pydantic import Field
from pydantic import StringConstraints

from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.infrastructure.label_languages import resolve_label

LOCALIZED_TEXT_MAX_LENGTH = 200
LOCALIZED_LONG_TEXT_MAX_LENGTH = 4000

LocalizedTextIn = Annotated[
    dict[str, Annotated[str, StringConstraints(max_length=LOCALIZED_TEXT_MAX_LENGTH)]],
    Field(max_length=10),
]

LocalizedLongTextIn = Annotated[
    dict[str, Annotated[str, StringConstraints(max_length=LOCALIZED_LONG_TEXT_MAX_LENGTH)]],
    Field(max_length=10),
]


def _resolve(value: Any) -> Any:
    if isinstance(value, (LocalizedText, dict)):
        return resolve_label(value)
    return value


ResolvedLabel = Annotated[str, BeforeValidator(_resolve)]
