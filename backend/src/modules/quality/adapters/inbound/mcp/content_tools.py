"""
The content of one controlled document for agents: a flow sequence step by
step with the names of the devices, positions and variants it uses, and a
saved calculation with its inputs and results. `controlled_documents` lists
the documents; these tools read one of them, looked up by its document
number as people name it, by its public id, or for a sequence by its
product and name.

A lookup by number or name runs the list use case of the web route with
that route's own parameter model, so another user's personal calculation
stays as hidden as it is in the web app, and the document is then read
through the route's own use case, which checks the caller may see it.
"""

from collections.abc import Callable
from collections.abc import Sequence
from typing import Any
from typing import Self
from typing import cast
from uuid import UUID

from pydantic import Field
from pydantic import model_validator

from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.infrastructure.label_languages import resolve_label
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_calculation_by_public_id_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import (
    get_calculation_revisions_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.calculations import get_calculation_use_case
from src.modules.quality.adapters.inbound.api.deps.calculations import get_calculations_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import (
    get_sequence_by_public_id_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequence_names_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequence_revisions_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequence_use_case
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequences_use_case
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationFilterParams,
)
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceFilterParams
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.controlled_document_dto import ControlledDocumentResult
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculation
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationByPublicId,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationRevisions,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculations
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequence
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceByPublicId
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceRevisions
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequences
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import SequenceNotFoundError

# Enough rows to hold every revision of the few documents a number or name
# matches; a lookup never pages.
_LOOKUP_LIMIT = 100

_DOCUMENT_NUMBER_HINT = (
    "The document number, exactly as Glados shows it, as controlled_documents lists it."
)
_REVISION_HINT = (
    "The revision to read, such as A or B. Without one, the latest revision is read, which "
    "may be a draft; the result lists every revision."
)


# ── Shared ────────────────────────────────────────────────────────────


def _status(document: ControlledDocumentResult) -> str:
    if document.invalid_at is not None:
        return "invalid"
    if document.superseded_at is not None:
        return "superseded"
    if document.released_at is not None:
        return "released"
    return "draft"


def _control(document: ControlledDocumentResult) -> dict[str, Any]:
    """The document control fields an agent needs to say which revision it
    read and whether that revision is in force."""
    return {
        "id": document.id,
        "public_id": document.public_id,
        "document_number": document.document_number,
        "revision": document.revision,
        "status": _status(document),
        "is_latest": document.is_latest,
        "revision_reason": document.revision_reason,
        "created": document.created,
        "creator_full_name": document.creator_full_name,
        "changed": document.changed,
        "changed_by_full_name": document.changed_by_full_name,
        "released_at": document.released_at,
        "released_by_full_name": document.released_by_full_name,
        "superseded_at": document.superseded_at,
        "invalid_at": document.invalid_at,
        "invalid_reason": document.invalid_reason,
        "locked_by_full_name": document.locked_by_full_name,
        "lock_expires_at": document.lock_expires_at,
    }


def _revisions(revisions: Sequence[ControlledDocumentResult]) -> list[dict[str, Any]]:
    return [
        {
            "revision": revision.revision,
            "status": _status(revision),
            "is_latest": revision.is_latest,
            "released_at": revision.released_at,
            "revision_reason": revision.revision_reason,
        }
        for revision in revisions
    ]


def _pick[D: ControlledDocumentResult](
    rows: Sequence[D],
    matches: Callable[[D], bool],
    revision: str | None,
    described: str,
    not_found: Callable[[str], Exception],
) -> D:
    """The one revision of the one document `matches` picks among `rows`,
    which hold every revision of every candidate."""
    candidates = [row for row in rows if matches(row)]
    if not candidates:
        raise not_found(f"No {described} found.")
    numbers = sorted({row.document_number for row in candidates})
    if len(numbers) > 1:
        raise InvalidInputError(
            f"Several documents match {described}: {', '.join(numbers)}. "
            "Name one by its document number."
        )
    if revision is None:
        latest = [row for row in candidates if row.is_latest]
        return latest[0] if latest else candidates[0]
    wanted = revision.strip().casefold()
    for row in candidates:
        if row.revision.casefold() == wanted:
            return row
    known = ", ".join(sorted(row.revision for row in candidates))
    raise not_found(f"{described} has no revision {revision}; it has {known}.")


class _ByNumber(ToolInput):
    public_id: UUID | None = Field(
        default=None,
        description="The document's public id, as search or controlled_documents return it.",
    )
    document_number: str | None = Field(
        default=None, min_length=1, max_length=200, description=_DOCUMENT_NUMBER_HINT
    )
    revision: str | None = Field(
        default=None, min_length=1, max_length=20, description=_REVISION_HINT
    )


# ── sequence ──────────────────────────────────────────────────────────


class SequenceInput(_ByNumber):
    product_id: int | None = Field(
        default=None,
        description=(
            "With name, the product the sequence belongs to, by its id (find it with search)."
        ),
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="With product_id, the sequence's name, such as Automatic cycle or Homing.",
    )

    @model_validator(mode="after")
    def _one_way_to_name_it(self) -> Self:
        by_name = self.product_id is not None or self.name is not None
        if by_name and (self.product_id is None or self.name is None):
            raise ValueError("A sequence by name needs both product_id and name.")
        if sum((self.public_id is not None, self.document_number is not None, by_name)) != 1:
            raise ValueError(
                "Name the sequence once: by public_id, by document_number, or by product_id "
                "and name."
            )
        return self


class _SequenceNames:
    """Reads the names a sequence shows (see freeze_names) for the ids its
    steps hold."""

    def __init__(self, names: dict[str, Any]) -> None:
        self._devices: dict[str, Any] = names.get("devices") or {}
        self._variants: dict[str, str] = names.get("variants") or {}

    @property
    def variants(self) -> list[str]:
        return list(self._variants.values())

    def device(self, device_id: int | None) -> str | None:
        if device_id is None:
            return None
        device = self._devices.get(str(device_id))
        return str(device["name"]) if device else f"device #{device_id}"

    def _position(self, device_id: int | None, position_id: int | None) -> dict[str, Any] | None:
        device = self._devices.get(str(device_id)) if device_id is not None else None
        if device is None or position_id is None:
            return None
        position: dict[str, Any] | None = (device.get("positions") or {}).get(str(position_id))
        return position

    def position(self, device_id: int | None, position_id: int | None) -> str | None:
        if position_id is None:
            return None
        position = self._position(device_id, position_id)
        if position is None:
            return f"position #{position_id}"
        return str(position.get("device_label") or resolve_label(position.get("label")))

    def unit(self, device_id: int | None, position_id: int | None) -> str | None:
        position = self._position(device_id, position_id)
        return None if position is None else position.get("unit")

    def value(self, raw: dict[str, Any] | None) -> dict[str, Any] | None:
        """A number that may differ per variant, with the variants named."""
        if raw is None:
            return None
        per_variant = {
            self._variants.get(str(variant_id), f"variant #{variant_id}"): value
            for variant_id, value in (raw.get("per_variant") or {}).items()
        }
        return _compact({"common": raw.get("common"), "per_variant": per_variant})

    def devices(self, device_ids: set[int]) -> list[dict[str, Any]]:
        """The devices the steps name, with their start state and the
        positions they can move to."""
        rows: list[dict[str, Any]] = []
        for key, device in self._devices.items():
            if int(key) not in device_ids:
                continue
            initial = device.get("initial_position_id")
            rows.append(
                _compact(
                    {
                        "device_id": int(key),
                        "name": device.get("name"),
                        "kind": resolve_label(device.get("kind")) or None,
                        "initial_position": self.position(int(key), initial),
                        "initial_position_value": device.get("initial_position_value"),
                        "driven_by": self.device(device.get("driven_by_id")),
                        "positions": [
                            _compact(
                                {
                                    "position": self.position(int(key), int(position_id)),
                                    "unit": position.get("unit"),
                                    "takes_value": position.get("takes_value"),
                                    "travel_time_ms": position.get("travel_time_ms"),
                                }
                            )
                            for position_id, position in (device.get("positions") or {}).items()
                        ],
                    }
                )
            )
        return rows


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """`data` without empty fields, so a step reads short."""
    return {key: value for key, value in data.items() if value not in (None, [], {})}


class _StepReader:
    """The steps of a sequence in words an agent can follow: numbered as
    the web app numbers them, devices and positions by name, transition
    targets by step number."""

    def __init__(self, steps: list[dict[str, Any]], names: _SequenceNames) -> None:
        self._steps = steps
        self._names = names
        self._numbers = {step["key"]: number for number, step in enumerate(steps, start=1)}
        self.device_ids: set[int] = set()

    def _term(self, term: dict[str, Any]) -> dict[str, Any]:
        device_id, position_id = term.get("device_id"), term.get("position_id")
        if device_id is not None:
            self.device_ids.add(device_id)
        step_key = term.get("step_key")
        return _compact(
            {
                "kind": term.get("kind"),
                "device": self._names.device(device_id),
                "position": self._names.position(device_id, position_id),
                "comparator": term.get("comparator"),
                "value": self._names.value(term.get("value")),
                "unit": self._names.unit(device_id, position_id),
                "step": self._numbers.get(step_key) if step_key else None,
                "duration_ms": self._names.value(term.get("duration_ms")),
                "text": term.get("text"),
            }
        )

    def _action(self, action: dict[str, Any]) -> dict[str, Any]:
        device_id, position_id = action.get("device_id"), action.get("position_id")
        if device_id is not None:
            self.device_ids.add(device_id)
        return _compact(
            {
                "kind": action.get("kind"),
                "qualifier": action.get("qualifier"),
                "device": self._names.device(device_id),
                "position": self._names.position(device_id, position_id),
                "value": self._names.value(action.get("value")),
                "unit": self._names.unit(device_id, position_id),
                "text": action.get("text"),
                "description": action.get("description"),
                "condition": [self._term(term) for term in action.get("condition") or ()],
                "duration_ms": self._names.value(action.get("duration_ms")),
            }
        )

    def _target(self, number: int, target: str) -> int | str:
        if target == "next":
            return number + 1
        if target == "end":
            return "end"
        return self._numbers.get(target, target)

    def steps(self) -> list[dict[str, Any]]:
        return [
            _compact(
                {
                    "step": number,
                    "description": step.get("description"),
                    "timeout_ms": step.get("timeout_ms"),
                    "expected_duration_ms": self._names.value(step.get("expected_duration_ms")),
                    "actions": [self._action(action) for action in step.get("actions") or ()],
                    "transitions": [
                        _compact(
                            {
                                "to_step": self._target(number, transition.get("target", "next")),
                                "condition": [
                                    self._term(term) for term in transition.get("condition") or ()
                                ],
                            }
                        )
                        for transition in step.get("transitions") or ()
                    ],
                }
            )
            for number, step in enumerate(self._steps, start=1)
        ]


async def _find_sequence(ctx: AgentToolContext, args: SequenceInput) -> SequenceResult:
    if args.public_id is not None:
        by_public_id = cast(
            GetSequenceByPublicId, await ctx.use_case(get_sequence_by_public_id_use_case)
        )
        found = await by_public_id.execute(actor=ctx.actor, public_id=args.public_id)
        if args.revision is None or found.revision.casefold() == args.revision.casefold():
            return found
        number = found.document_number
        params = SequenceFilterParams(limit=_LOOKUP_LIMIT, search=number, all_revisions=True)
    elif args.document_number is not None:
        number = args.document_number.strip()
        params = SequenceFilterParams(limit=_LOOKUP_LIMIT, search=number, all_revisions=True)
    else:
        number = None
        params = SequenceFilterParams(
            limit=_LOOKUP_LIMIT, product_id=args.product_id, search=args.name, all_revisions=True
        )
    sequences = cast(GetSequences, await ctx.use_case(get_sequences_use_case))
    page = await sequences.execute(actor=ctx.actor, query=params.to_query())
    if number is not None:
        wanted = number.casefold()
        row = _pick(
            page.items,
            lambda r: r.document_number.casefold() == wanted,
            args.revision,
            f"sequence {number}",
            SequenceNotFoundError,
        )
    else:
        name = " ".join((args.name or "").split()).casefold()
        row = _pick(
            page.items,
            lambda r: r.name.casefold() == name,
            args.revision,
            f"sequence {args.name!r} of product #{args.product_id}",
            SequenceNotFoundError,
        )
    one = cast(GetSequence, await ctx.use_case(get_sequence_use_case))
    return await one.execute(actor=ctx.actor, sequence_id=row.id)


async def _sequence(ctx: AgentToolContext, args: SequenceInput) -> ToolOutput:
    sequence = await _find_sequence(ctx, args)
    names_use_case = await ctx.use_case(get_sequence_names_use_case)
    names = _SequenceNames(await names_use_case.execute(actor=ctx.actor, sequence_id=sequence.id))
    reader = _StepReader(sequence.steps, names)
    steps = reader.steps()
    revisions_use_case = cast(
        GetSequenceRevisions, await ctx.use_case(get_sequence_revisions_use_case)
    )
    revisions = await revisions_use_case.execute(actor=ctx.actor, sequence_id=sequence.id)
    return ToolOutput(
        {
            "sequence": {
                **_control(sequence),
                "name": sequence.name,
                "product_id": sequence.product_id,
                "product_number": sequence.product_number,
                "step_count": sequence.step_count,
                # Released revisions show the names frozen at their release;
                # a draft shows the devices' current names.
                "names_frozen": sequence.frozen is not None,
                "variants": names.variants,
            },
            "devices": names.devices(reader.device_ids),
            "steps": steps,
            "revisions": _revisions(revisions),
        }
    )


SEQUENCE_TOOL = AgentTool(
    name="sequence",
    title="Flow sequence",
    description=(
        "One flow sequence of a product (such as its automatic cycle or homing) step by step: "
        "each step's actions (which device moves to which position, with values per product "
        "variant, or a described action), how long each applies (stored, continuous or pulse), "
        "the transitions to the next step with their conditions, timeouts and expected times, "
        "and the devices it moves with their initial positions. Devices and positions are "
        "named, steps numbered as in Glados. A released revision shows the names frozen at its "
        "release, a draft the current ones. Read two revisions to compare them. Find the "
        "sequences of a product with controlled_documents."
    ),
    input_model=SequenceInput,
    handler=_sequence,
)


# ── calculation ───────────────────────────────────────────────────────


class CalculationInput(_ByNumber):
    include_inputs: bool = Field(
        default=True, description="Include the inputs the calculation was made from."
    )
    include_results: bool = Field(
        default=True, description="Include the saved results of the calculation."
    )

    @model_validator(mode="after")
    def _one_way_to_name_it(self) -> Self:
        if (self.public_id is None) == (self.document_number is None):
            raise ValueError("Name the calculation once: by public_id or by document_number.")
        return self


async def _find_calculation(ctx: AgentToolContext, args: CalculationInput) -> CalculationResult:
    if args.public_id is not None:
        by_public_id = cast(
            GetCalculationByPublicId, await ctx.use_case(get_calculation_by_public_id_use_case)
        )
        found = await by_public_id.execute(actor=ctx.actor, public_id=args.public_id)
        if args.revision is None or found.revision.casefold() == args.revision.casefold():
            return found
        number = found.document_number
    else:
        number = (args.document_number or "").strip()
    calculations = cast(GetCalculations, await ctx.use_case(get_calculations_use_case))
    params = CalculationFilterParams(limit=_LOOKUP_LIMIT, search=number, all_revisions=True)
    page = await calculations.execute(actor=ctx.actor, query=params.to_query())
    wanted = number.casefold()
    row = _pick(
        page.items,
        lambda r: r.document_number.casefold() == wanted,
        args.revision,
        f"calculation {number}",
        CalculationNotFoundError,
    )
    one = cast(GetCalculation, await ctx.use_case(get_calculation_use_case))
    return await one.execute(actor=ctx.actor, calculation_id=row.id)


def _owner(calculation: CalculationResult) -> str:
    if calculation.project_id is not None:
        return "project"
    if calculation.product_id is not None:
        return "product"
    return "personal"


async def _calculation(ctx: AgentToolContext, args: CalculationInput) -> ToolOutput:
    calculation = await _find_calculation(ctx, args)
    revisions_use_case = cast(
        GetCalculationRevisions, await ctx.use_case(get_calculation_revisions_use_case)
    )
    revisions = await revisions_use_case.execute(actor=ctx.actor, calculation_id=calculation.id)
    data: dict[str, Any] = {
        "calculation": {
            **_control(calculation),
            "tool": calculation.tool,
            "title": calculation.title,
            "note": calculation.note,
            "owner": _owner(calculation),
            "project_number": calculation.project_number,
            "product_number": calculation.product_number,
            "device": calculation.product_device_name,
            "input_version": calculation.input_version,
            "engine_version": calculation.engine_version,
        },
        "revisions": _revisions(revisions),
    }
    if args.include_inputs:
        data["inputs"] = calculation.inputs
    if args.include_results:
        data["results"] = calculation.results
    return ToolOutput(data)


CALCULATION_TOOL = AgentTool(
    name="calculation",
    title="Saved calculation",
    description=(
        "One saved calculation of an engineering tool (such as drive sizing or safety "
        "distance), by its document number or public id: the tool, title and note, whether it "
        "is personal or belongs to a project or product, the device it is about, its revision "
        "and release state, and its inputs and results. The results are the snapshot the tool "
        "computed in the browser when the calculation was saved, with the input and engine "
        "versions that produced them; Glados does not compute them again, so a tool changed "
        "since may now give other results. Another user's personal calculation is not found. "
        "Find the calculations of a project or product with controlled_documents."
    ),
    input_model=CalculationInput,
    handler=_calculation,
)
