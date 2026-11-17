"""The ordered decision table every lifecycle status is derived by.

A table is a list of rows tried in order, and the first row whose condition
holds gives the result. The table ends with a fallback row that holds for any
input, so every input has exactly one result and a derivation never fails.
Each row carries its condition and result as text next to the code that
evaluates them, so a listing of the rows shows what the code runs.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

OTHERWISE = "otherwise"


@dataclass(frozen=True)
class DerivationRule[F, R]:
    """One row of a table. `applies` decides whether the row matches the
    facts and `outcome` gives its result, which is one of `results`. Most
    rows have a constant result; a row whose result depends on the facts,
    such as an order without lines, computes it in `outcome`."""

    number: int
    condition: str
    result: str
    results: tuple[R, ...]
    applies: Callable[[F], bool]
    outcome: Callable[[F], R]


@dataclass(frozen=True)
class Derivation[R]:
    """A derived value and the number of the row that produced it."""

    value: R
    rule: int


@dataclass(frozen=True)
class DerivationTable[F, R]:
    """Rows tried in order, then the fallback. `key` names the table, for
    example in a drift report or a catalogue of the lifecycles."""

    key: str
    rules: tuple[DerivationRule[F, R], ...]
    fallback: DerivationRule[F, R]

    def __post_init__(self) -> None:
        numbers = [row.number for row in self.rows]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"Rows of {self.key} must be numbered from 1 in order, got {numbers}.")
        if self.fallback.condition != OTHERWISE:
            raise ValueError(f"The last row of {self.key} must be the fallback row.")

    @property
    def rows(self) -> tuple[DerivationRule[F, R], ...]:
        """Every row in evaluation order, the fallback last."""
        return (*self.rules, self.fallback)

    def derive(self, facts: F) -> Derivation[R]:
        for row in self.rules:
            if row.applies(facts):
                return Derivation(value=row.outcome(facts), rule=row.number)
        return Derivation(value=self.fallback.outcome(facts), rule=self.fallback.number)


def rule[F, R: Enum](
    number: int, condition: str, result: R, applies: Callable[[F], bool]
) -> DerivationRule[F, R]:
    """A row with a constant result, described by the result's value."""
    return DerivationRule(
        number=number,
        condition=condition,
        result=str(result.value),
        results=(result,),
        applies=applies,
        outcome=lambda _facts: result,
    )


def otherwise[F, R: Enum](number: int, result: R) -> DerivationRule[F, R]:
    """The fallback row, which holds for any input."""
    return rule(number, OTHERWISE, result, lambda _facts: True)
