"""The generic intent table: which user actions an aggregate accepts, as one
table of rules per aggregate. The planning and fulfillment aggregates define
their tables in domain/services/lifecycle/intents.py, projects next to the
project rules in domain/services/lifecycle/project.py.

An intent rule names an action, the statuses it starts from, a guard on the
aggregate and its context, and a guard on the actor. `allowed_actions`
returns every action whose guards all pass, `blocked_actions` every action
the state allows but the actor's guard refuses, with the permission it
lacks, and `check` tells why one action is refused. All of them read the
same rules, so a use case that guards an action and a response that offers
it cannot disagree. `check` reports a missing
permission before a wrong state, so a caller without the permission learns
nothing about the aggregate's state.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class HasStatus(Protocol):
    """The aggregate an intent applies to; its entity satisfies this."""

    @property
    def status(self) -> str: ...


class RefusalKind(Enum):
    """PERMISSION means the actor may not take the action (HTTP 403 for a use
    case); STATE means the aggregate does not allow it now (409)."""

    PERMISSION = "permission"
    STATE = "state"


@dataclass(frozen=True)
class IntentRefusal:
    """Why an action is refused. `requirement` says what the action needs.
    For a state refusal `failed` is the part of it that does not hold now
    and `by_status` says whether that part is the status the action starts
    from."""

    action: LifecycleAction
    kind: RefusalKind
    requirement: str
    failed: str = ""
    by_status: bool = False

    def message(self, subject: str, status: str, verb: str) -> str:
        """The refusal as a sentence about `subject`, such as "Lot #3",
        whose current status is `status`, for an action named by `verb`."""
        failed = self.failed or self.requirement
        if self.by_status:
            return f"{subject} is {status}; to {verb} it needs {failed}."
        return f"{subject} is {status}, but to {verb} it needs {failed}."


def _anyone(_actor: User, _subject: object, _context: object) -> bool:
    return True


def _no_guard(_subject: object, _context: object) -> bool:
    return True


@dataclass(frozen=True)
class Check[S, C]:
    """One named condition of an intent rule, so a refusal can name the
    condition that does not hold."""

    text: str
    test: Callable[[S, C], bool]


@dataclass(frozen=True, kw_only=True)
class IntentRule[S: HasStatus, C]:
    """One action of an aggregate. `allowed_from` lists the status values the
    action starts from, None for any status; `guard` checks the rest of the
    state on the subject and its context; `permitted` checks the actor,
    who may depend on the subject and its context, such as the status of a
    line's order. `permission` describes that actor guard as text for the
    rule listings, and `needs` names the permission it refuses without, so
    a client can show the action disabled and say what is missing. A rule
    with an actor guard must name both. A rule whose state needs several
    conditions lists them as `checks` instead of one `condition` and
    `guard`; its condition is then their texts and its guard all of
    them. A rule with checks may
    still name a `condition` that its use case checks on facts the context
    does not carry; it follows the checks' texts and refuses nothing here."""

    action: LifecycleAction
    allowed_from: tuple[str, ...] | None
    effect: str
    condition: str = ""
    guard: Callable[[S, C], bool] = _no_guard
    checks: tuple[Check[S, C], ...] = ()
    permission: str = ""
    needs: str = ""
    permitted: Callable[[User, S, C], bool] = _anyone

    def __post_init__(self) -> None:
        if self.permitted is not _anyone and not (self.permission and self.needs):
            raise ValueError(
                f"{self.action.value}: an actor guard needs a permission text and `needs`."
            )
        if not self.checks:
            return
        if self.guard is not _no_guard:
            raise ValueError(f"{self.action.value}: give either checks or a guard.")
        texts = [c.text for c in self.checks]
        if self.condition:
            texts.append(self.condition)
        object.__setattr__(self, "condition", "; ".join(texts))
        object.__setattr__(
            self, "guard", lambda subject, context: self._failed_check(subject, context) is None
        )

    def _failed_check(self, subject: S, context: C) -> str | None:
        return next((c.text for c in self.checks if not c.test(subject, context)), None)

    @property
    def requirement(self) -> str:
        """The state the action needs, as text."""
        parts = []
        if self.allowed_from is not None:
            parts.append("status " + " or ".join(self.allowed_from))
        if self.condition:
            parts.append(self.condition)
        return "; ".join(parts) if parts else "no state requirement"

    def state_allows(self, subject: S, context: C) -> bool:
        """Whether the subject's state allows the action now, whoever takes
        it: its status is one the action starts from and its guard passes."""
        if self.allowed_from is not None and subject.status not in self.allowed_from:
            return False
        return self.guard(subject, context)

    def refusal(self, subject: S, context: C, actor: User) -> IntentRefusal | None:
        """None when the actor may take the action on the subject now."""
        if not self.permitted(actor, subject, context):
            return IntentRefusal(self.action, RefusalKind.PERMISSION, self.permission)
        if self.allowed_from is not None and subject.status not in self.allowed_from:
            return IntentRefusal(
                self.action,
                RefusalKind.STATE,
                self.requirement,
                failed="status " + " or ".join(self.allowed_from),
                by_status=True,
            )
        if not self.guard(subject, context):
            failed = (self._failed_check(subject, context) if self.checks else None) or (
                self.condition or self.requirement
            )
            return IntentRefusal(self.action, RefusalKind.STATE, self.requirement, failed=failed)
        return None


@dataclass(frozen=True)
class IntentTable[S: HasStatus, C]:
    """The actions of one aggregate, each at most once, in display order."""

    key: str
    rules: tuple[IntentRule[S, C], ...]

    def __post_init__(self) -> None:
        actions = [r.action for r in self.rules]
        if len(actions) != len(set(actions)):
            raise ValueError(f"Each action may appear once in {self.key}, got {actions}.")

    def rule_for(self, action: LifecycleAction) -> IntentRule[S, C] | None:
        return next((r for r in self.rules if r.action == action), None)

    def allowed_actions(self, subject: S, context: C, actor: User) -> tuple[LifecycleAction, ...]:
        """Every action the actor may take on the subject now, in table order."""
        return tuple(r.action for r in self.rules if r.refusal(subject, context, actor) is None)

    def blocked_actions(self, subject: S, context: C, actor: User) -> dict[LifecycleAction, str]:
        """Every action the subject's state allows now but the actor's guard
        refuses, in table order, each with the permission the actor lacks.
        An action the state refuses is in neither this nor `allowed_actions`."""
        return {
            r.action: r.needs
            for r in self.rules
            if r.state_allows(subject, context) and not r.permitted(actor, subject, context)
        }

    def check(
        self, action: LifecycleAction, subject: S, context: C, actor: User
    ) -> IntentRefusal | None:
        """None when the action is allowed, else why it is refused. An action
        that is not in the table is refused as a state refusal."""
        found = self.rule_for(action)
        if found is None:
            return IntentRefusal(
                action, RefusalKind.STATE, f"{action.value} is not an action of {self.key}"
            )
        return found.refusal(subject, context, actor)
