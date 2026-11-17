"""
Every row of the state machine catalogue has its translation in both
frontend locale files. The handbook shows a rule or an action by its
`text_key`, never by the English text of the code, so a row without a key
would show a raw key path in the handbook. The keys come from the
catalogue itself (catalogue_text_keys); the fixed labels of the handbook
tables, every lifecycle action and the order line actions the gated
frontend shows are listed here. Each namespace lives in its own locale
file (locales/<namespace>/<namespace>.<locale>.ts), read as text; the reader
refuses to pass when it finds no such block or no keys in it, so a change of
the files' layout cannot make the test pass without checking anything.
"""

import re
from pathlib import Path

import pytest

from src.read.domain.services.state_machine_catalog import SET_STATUS
from src.read.domain.services.state_machine_catalog import catalogue_text_keys
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

_LOCALES = Path(__file__).resolve().parents[3] / "frontend" / "src" / "core" / "i18n" / "locales"
_KEY = r"(?:[A-Za-z_$][\w$]*|'[^']*'|\"[^\"]*\")"
_OPEN = re.compile(rf"^(\s*)({_KEY})\s*:\s*\{{\s*$")
_LEAF = re.compile(rf"^(\s*)({_KEY})\s*:")
_CLOSE = re.compile(r"^\s*\}\s*,?\s*$")


def _unquote(key: str) -> str:
    return key[1:-1] if key[:1] in "'\"" else key


def block_keys(text: str, block: str) -> set[str]:
    """The key paths below the top-level `block` of a locale file, for
    example `rows.lot_status.r1` below `stateMachines`. Raises when the
    block is missing or holds no keys."""
    lines = text.splitlines()
    opening = re.compile(rf"^\s{{2}}{re.escape(block)}\s*:\s*\{{\s*$")
    start = next((i for i, line in enumerate(lines) if opening.match(line)), None)
    if start is None:
        raise AssertionError(f"No top-level `{block}: {{` block in the locale file.")
    stack: list[str] = []
    keys: set[str] = set()
    for line in lines[start + 1 :]:
        if _CLOSE.match(line):
            if not stack:
                break
            stack.pop()
            continue
        opened = _OPEN.match(line)
        if opened:
            stack.append(_unquote(opened.group(2)))
            continue
        leaf = _LEAF.match(line)
        if leaf:
            keys.add(".".join([*stack, _unquote(leaf.group(2))]))
    if not keys:
        raise AssertionError(f"The `{block}` block of the locale file holds no keys.")
    return keys


def namespace_text(namespace: str, locale: str) -> str:
    """The namespace file of `locale` rewritten as a top-level `namespace`
    block, the shape block_keys reads. Raises when the file has no default
    export."""
    path = _LOCALES / namespace / f"{namespace}.{locale}.ts"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line == "export default {"), None)
    if start is None:
        raise AssertionError(f"No `export default {{` in {path}.")
    return "\n".join([f"  {namespace}: {{", *lines[start + 1 :]])


def state_machine_keys(text: str) -> set[str]:
    """The key paths below the top-level `stateMachines` block."""
    return block_keys(text, "stateMachines")


# The fixed labels of the handbook's state machine tables, below
# `stateMachines`, and every action label, the status moves included.
FIXED_STATE_MACHINE_KEYS = [
    "liveHint",
    "kind.derived",
    "kind.intent",
    "rules.title",
    "rules.intro",
    "rules.columns.number",
    "rules.columns.condition",
    "rules.columns.result",
    "intents.title",
    "intents.anyStatus",
    "intents.setStatus",
    "intents.columns.action",
    "intents.columns.allowedFrom",
    "intents.columns.condition",
    "intents.columns.permission",
    "intents.columns.effect",
    *(f"actions.{action.value}" for action in LifecycleAction),
    f"actions.{SET_STATUS}",
]

# The order line actions the gated frontend shows, below `orders`.
ORDER_KEYS = [
    "actions.cancelItem",
    "actions.cancelItemConfirm",
    "actions.cancelItemSuccess",
    "actions.closeShort",
    "actions.closeShortConfirm",
    "actions.closeShortSuccess",
    "delivery.correct.title",
    "delivery.correct.quantity",
    "delivery.correct.reason",
    "delivery.correct.submit",
    "delivery.correct.success",
    "items.deliveryHistory.columns.correction",
]


def test_the_reader_finds_nested_keys_and_refuses_an_empty_or_missing_block():
    text = (
        "export default {\n"
        "  stateMachines: {\n"
        "    rows: {\n"
        "      lot_status: {\n"
        "        r1: 'Someone canceled the lot.',\n"
        "        'r2Result':\n"
        "          'Long text',\n"
        "      },\n"
        "    },\n"
        "    refresh: 'Refresh',\n"
        "  },\n"
        "  other: {\n"
        "    key: 'x',\n"
        "  },\n"
        "}\n"
    )
    assert state_machine_keys(text) == {
        "rows.lot_status.r1",
        "rows.lot_status.r2Result",
        "refresh",
    }
    assert block_keys(text, "other") == {"key"}
    with pytest.raises(AssertionError, match="No top-level"):
        state_machine_keys("export default {\n  other: {\n    key: 'x',\n  },\n}\n")
    with pytest.raises(AssertionError, match="holds no keys"):
        state_machine_keys("export default {\n  stateMachines: {\n  },\n}\n")


@pytest.mark.parametrize("locale", ["en-GB", "de-AT"])
def test_every_catalogue_row_has_its_text_in_the_locale(locale):
    expected = catalogue_text_keys()
    assert expected, "The catalogue lists no text keys."
    present = state_machine_keys(namespace_text("stateMachines", locale))
    missing = [key for key in expected if key not in present]
    assert missing == [], f"{locale}.ts lacks stateMachines keys: {missing}"


@pytest.mark.parametrize("locale", ["en-GB", "de-AT"])
def test_the_fixed_handbook_labels_and_every_action_have_their_text(locale):
    present = state_machine_keys(namespace_text("stateMachines", locale))
    missing = [key for key in FIXED_STATE_MACHINE_KEYS if key not in present]
    assert missing == [], f"{locale}.ts lacks stateMachines keys: {missing}"


@pytest.mark.parametrize("locale", ["en-GB", "de-AT"])
def test_the_order_line_actions_have_their_text(locale):
    present = block_keys(namespace_text("orders", locale), "orders")
    missing = [key for key in ORDER_KEYS if key not in present]
    assert missing == [], f"{locale}.ts lacks orders keys: {missing}"
