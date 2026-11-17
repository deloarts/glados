"""
Rules of the MCP surface, through which a user's AI agent reads Glados and
prepares drafts on the user's behalf. They decide which browser origins may
call it, how long a token that reaches it may live, when an unused one is
revoked, and what a tool result may carry once it leaves for the agent's
model provider. No I/O.
"""

import re
from collections.abc import Mapping
from datetime import datetime
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.agent_consent import AgentConsent
from src.modules.platform.domain.value_objects.permission import Permission

# ── Origins ─────────────────────────────────────────────────────────────


def normalise_allowed_origins(entries: list[str]) -> list[str]:
    """Strips, drops empties and duplicates (order kept) and validates every
    entry as a bare http(s) origin such as `https://glados.example.com`.

    Raises ValueError naming the first bad entry, surfaced as a 422 by the
    Pydantic field validator that calls this.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in entries:
        entry = raw.strip().rstrip("/").lower()
        if not entry or entry in seen:
            continue
        parts = urlsplit(entry)
        if (
            parts.scheme not in ("http", "https")
            or not parts.netloc
            or parts.path
            or parts.query
            or parts.fragment
        ):
            raise ValueError(f"{raw!r} is not an origin such as https://host[:port].")
        seen.add(entry)
        result.append(entry)
    return result


def origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    """Whether a request with this `Origin` header may call the surface. Agent
    clients send none and pass. A browser always sends one, and only the
    listed origins pass, which keeps a web page from driving a user's agent
    token through DNS rebinding or a local proxy."""
    if origin is None:
        return True
    return origin.strip().rstrip("/").lower() in allowed_origins


# ── Token lifetime ──────────────────────────────────────────────────────


def is_agent_token(permissions: list[str]) -> bool:
    """Whether a token with these permissions reaches the MCP surface."""
    return Permission.USE_MCP in permissions


def agent_token_lifetime_cap(general_cap_days: int, agent_cap_days: int) -> int:
    """The lifetime cap of a new agent token. The agent cap always holds,
    also while the general cap is lifted (0), and the stricter of the two
    wins otherwise."""
    if general_cap_days <= 0:
        return agent_cap_days
    return min(general_cap_days, agent_cap_days)


def idle_since(created: datetime, last_used: datetime | None) -> datetime:
    """The instant from which an agent token counts as unused."""
    return last_used if last_used is not None and last_used > created else created


def is_idle(created: datetime, last_used: datetime | None, now: datetime, idle_days: int) -> bool:
    """Whether an agent token has gone unused for `idle_days` or longer."""
    return now - idle_since(created, last_used) >= timedelta(days=idle_days)


# ── Approval and consent ────────────────────────────────────────────────

# Raised whenever the consent dialog text changes in a way users must
# confirm again; a confirmation of an older version stops the user's agent
# tokens until they confirm the current one.
AGENT_CONSENT_VERSION = 1


def consent_terms_changed(previous: AdminAgentSettings, current: AdminAgentSettings) -> bool:
    """Whether the settings changed something a user's consent covers: the
    approved providers, the AI policy, or whether names of people or prices
    leave in tool results."""
    return (
        previous.approved_providers.strip() != current.approved_providers.strip()
        or previous.ai_policy_url != current.ai_policy_url
        or previous.include_person_names != current.include_person_names
        or previous.include_costs != current.include_costs
    )


def consent_is_current(consent: AgentConsent | None, settings: AdminAgentSettings) -> bool:
    """Whether a user's confirmation covers the terms in force: it confirms
    the current text and was given after the company's approval was last
    recorded."""
    if consent is None or settings.processing_approved_at is None:
        return False
    return (
        consent.consent_version == AGENT_CONSENT_VERSION
        and consent.consented_at >= settings.processing_approved_at
    )


# ── What a result may carry ─────────────────────────────────────────────

# The keys that name a person. A key matches when it is one of these or
# ends in one of them after an underscore, such as `operator_full_name`.
_PERSON_KEY_ENDINGS: tuple[str, ...] = (
    "full_name",
    "username",
    "user_name",
    "display_name",
    "email",
    "e_mail",
    "phone",
    "contact_name",
    "contact_person",
    "first_name",
    "last_name",
    "initials",
    # Who did something, as `planned_by_name` or `ordered_by_name`.
    "by_name",
)

# The keys that carry money, matched on whole words of a snake case key,
# so `unit_price` and `extra_costs` match and `priority` does not. Generic
# words such as `value` or `total` are left out on purpose: a KPI value or a
# total quantity is not money.
_COST_WORDS: frozenset[str] = frozenset(
    {
        "price",
        "prices",
        "cost",
        "costs",
        "amount",
        "amounts",
        "currency",
        "discount",
        "discounts",
        "surcharge",
        "surcharges",
        "budget",
    }
)

# Whole keys that carry money without a money word, the sums of an order
# or a quote request and the dashboard's spend.
_COST_KEYS: frozenset[str] = frozenset(
    {"net_total", "gross_total", "lines_total", "total_net", "total_gross", "spend"}
)

# Words that make a cost-looking key harmless again, such as the hours of a
# cost centre or a count of amounts.
_NOT_MONEY_WORDS: frozenset[str] = frozenset({"quantity", "qty", "count", "hours", "minutes"})

# Keys whose values are free text histories, such as an item's changelog,
# whose entries name the person behind each change and may quote old and
# new prices. Redaction by key cannot see inside them, so they are dropped
# unless both names and money may leave.
_HISTORY_KEYS: frozenset[str] = frozenset({"changes", "changelog", "change_log"})

REDACTED = "[hidden]"

_WORD_SPLIT = re.compile(r"[_\W]+")


def is_person_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        lowered == ending or lowered.endswith(f"_{ending}") for ending in _PERSON_KEY_ENDINGS
    )


def is_cost_key(key: str) -> bool:
    if key.lower() in _COST_KEYS:
        return True
    words = {w for w in _WORD_SPLIT.split(key.lower()) if w}
    return bool(words & _COST_WORDS) and not words & _NOT_MONEY_WORDS


def redact(value: Any, *, include_person_names: bool, include_costs: bool) -> Any:
    """A copy of a JSON-shaped tool result without the names of people and
    without money, unless the settings let them in.

    A person field keeps its key and reads `[hidden]` (null stays null), so
    the agent still sees that a lot has an operator. A money field is
    dropped with its key, because a placeholder in a number field would
    mislead a model that adds things up. A free text history such as a
    changelog is dropped unless both may leave.
    """
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            k = str(key)
            if k.lower() in _HISTORY_KEYS and not (include_person_names and include_costs):
                continue
            if not include_costs and is_cost_key(k):
                continue
            if not include_person_names and is_person_key(k):
                out[k] = None if item is None else REDACTED
                continue
            out[k] = redact(
                item, include_person_names=include_person_names, include_costs=include_costs
            )
        return out
    if isinstance(value, list):
        return [
            redact(item, include_person_names=include_person_names, include_costs=include_costs)
            for item in value
        ]
    return value


def redaction_flags(settings: AdminAgentSettings) -> dict[str, bool]:
    """The redaction switches of the settings, as `redact` takes them."""
    return {
        "include_person_names": settings.include_person_names,
        "include_costs": settings.include_costs,
    }
