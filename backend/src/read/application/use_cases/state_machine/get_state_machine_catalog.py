"""
Maps the domain catalogue of lifecycles (src/domain/services/
state_machine_catalog.py) onto the API-facing DTOs. No repository and no
I/O: the catalogue is read from the live derivation and intent tables on
every call, so nothing here is cached.
"""

from src.read.application.dto.state_machine_dto import StateMachineCatalogDTO
from src.read.application.dto.state_machine_dto import StateMachineDTO
from src.read.application.dto.state_machine_dto import StateMachineEdgeDTO
from src.read.application.dto.state_machine_dto import StateMachineImplicationDTO
from src.read.application.dto.state_machine_dto import StateMachineIntentDTO
from src.read.application.dto.state_machine_dto import StateMachineRuleDTO
from src.read.application.dto.state_machine_dto import StateMachineStateDTO
from src.read.application.dto.state_machine_dto import StateMachineTransitionDTO
from src.read.domain.services.state_machine_catalog import MachineGraph
from src.read.domain.services.state_machine_catalog import MachineKind
from src.read.domain.services.state_machine_catalog import build_state_machine_catalog


class GetStateMachineCatalog:
    async def execute(self) -> StateMachineCatalogDTO:
        return StateMachineCatalogDTO(
            machines=[_to_dto(graph) for graph in build_state_machine_catalog()]
        )


def _to_dto(graph: MachineGraph) -> StateMachineDTO:
    return StateMachineDTO(
        key=graph.key,
        entity=graph.entity,
        kind="derived" if graph.kind is MachineKind.DERIVED else "intent",
        description=graph.description,
        states=[
            StateMachineStateDTO(value=s.value, initial=s.initial, terminal=s.terminal)
            for s in graph.states
        ],
        edges=[
            StateMachineEdgeDTO(from_state=e.from_state, to_state=e.to_state) for e in graph.edges
        ],
        rules=[
            StateMachineRuleDTO(
                number=r.number,
                text_key=r.text_key,
                condition=r.condition,
                result=r.result,
                results=list(r.results),
                result_text_key=r.result_text_key,
            )
            for r in graph.rules
        ],
        intents=[
            StateMachineIntentDTO(
                action=i.action,
                text_key=i.text_key,
                allowed_from=list(i.allowed_from) if i.allowed_from is not None else None,
                condition=i.condition,
                permission=i.permission,
                effect=i.effect,
                target=i.target,
            )
            for i in graph.intents
        ],
        transitions=[
            StateMachineTransitionDTO(
                from_state=t.from_state,
                to_state=t.to_state,
                trigger=t.trigger,
                subject=t.subject,
                cascade=t.cascade,
                rule_text_keys=list(t.rule_text_keys),
                intent_text_keys=list(t.intent_text_keys),
                implications=[
                    StateMachineImplicationDTO(
                        machine=i.machine, from_state=i.from_state, to_state=i.to_state
                    )
                    for i in t.implications
                ],
            )
            for t in graph.transitions
        ],
    )
