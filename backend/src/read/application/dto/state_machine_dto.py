"""
DTOs of the state machine catalogue: each machine's states, edges,
derivation rows and actions.
"""

from typing import Literal

from src.modules.platform.application.dto.base import ResultModel


class StateMachineStateDTO(ResultModel):
    value: str
    initial: bool
    terminal: bool


class StateMachineEdgeDTO(ResultModel):
    from_state: str
    to_state: str


class StateMachineRuleDTO(ResultModel):
    """One row of a derivation table, in evaluation order. `results` lists
    the statuses the row can give; `result_text_key` is set when it can give
    several and names the text that says which."""

    number: int
    text_key: str
    condition: str
    result: str
    results: list[str]
    result_text_key: str | None


class StateMachineIntentDTO(ResultModel):
    """One user action. `allowed_from` is None when the action starts from
    any status; `target` is the status a status move sets, None for a
    lifecycle action."""

    action: str
    text_key: str
    allowed_from: list[str] | None
    condition: str
    permission: str
    effect: str
    target: str | None


class StateMachineImplicationDTO(ResultModel):
    machine: str
    from_state: str | None
    to_state: str


class StateMachineTransitionDTO(ResultModel):
    """One status change the code makes; see
    src/read/domain/services/state_machine_catalog.py TransitionRow."""

    from_state: str | None
    to_state: str
    trigger: str
    subject: str
    cascade: bool
    rule_text_keys: list[str]
    intent_text_keys: list[str]
    implications: list[StateMachineImplicationDTO]


class StateMachineDTO(ResultModel):
    key: str
    entity: str
    kind: Literal["derived", "intent"]
    description: str | None
    states: list[StateMachineStateDTO]
    edges: list[StateMachineEdgeDTO]
    rules: list[StateMachineRuleDTO]
    intents: list[StateMachineIntentDTO]
    transitions: list[StateMachineTransitionDTO]


class StateMachineCatalogDTO(ResultModel):
    machines: list[StateMachineDTO]
