"""
What Workspace offers agents: where a project or a product stands, looked
up by its number, the devices of a product with what is still missing on
them, what renumbering a product would affect, the meetings of a project or
product, and drafts of meeting notes for the user to review.
"""

from typing import Any

from pydantic import Field

from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.infrastructure.label_languages import resolve_label
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_completeness_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_kinds_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_options_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_devices_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_renumber_impact_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_summary_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_actions
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_summary_use_case
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import (
    ProductRenumberImpactResponse,
)
from src.modules.workspace.adapters.inbound.mcp.meeting_tools import MEETING_TOOLS
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceComponentResult
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceResult
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceKindResult,
)
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.application.use_cases.product_device.completeness import (
    DeviceCompleteness,
)
from src.modules.workspace.application.use_cases.product_device.completeness import SequenceCoverage
from src.modules.workspace.domain.entities.product_device_check import ProductDeviceCheck
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.modules.workspace.domain.value_objects.device_plan import required_plans


async def _product(ctx: AgentToolContext, product_number: str) -> ProductResult:
    use_case = await ctx.use_case(get_product_by_number_use_case)
    return await use_case.execute(product_number=product_number)


# ── project_status ────────────────────────────────────────────────────


class ProjectStatusInput(ToolInput):
    project_number: str = Field(
        min_length=1,
        max_length=200,
        description="The project number, exactly as Glados shows it.",
    )


async def _project_status(ctx: AgentToolContext, args: ProjectStatusInput) -> ToolOutput:
    use_case = await ctx.use_case(get_project_by_number_use_case)
    project = await use_case.execute(number=args.project_number)
    actions = await ctx.use_case(get_project_actions)
    await actions.projects([project], ctx.actor)
    summary_use_case = await ctx.use_case(get_project_summary_use_case)
    summary = await summary_use_case.execute(project.id)
    return ToolOutput({"project": project, "summary": summary})


# ── product_status ────────────────────────────────────────────────────


class ProductStatusInput(ToolInput):
    product_number: str = Field(
        min_length=1,
        max_length=200,
        description="The product number, exactly as Glados shows it.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="The most devices to return in the device completeness list.",
    )


async def _product_status(ctx: AgentToolContext, args: ProductStatusInput) -> ToolOutput:
    product = await _product(ctx, args.product_number)
    summary_use_case = await ctx.use_case(get_product_summary_use_case)
    summary = await summary_use_case.execute(product.id)
    devices_use_case = await ctx.use_case(get_product_devices_use_case)
    names = {d.id: d.full_name_utf8 for d in await devices_use_case.execute(product.id, False)}
    completeness_use_case = await ctx.use_case(get_product_device_completeness_use_case)
    completeness = await completeness_use_case.execute(product.id)
    return ToolOutput(
        {
            "product": product,
            "summary": summary,
            "device_count": len(completeness),
            "devices": [
                {
                    "device_id": c.device_id,
                    "device_name": names.get(c.device_id),
                    "sequence_coverage": c.sequence_coverage,
                    "plans_checked": [
                        {
                            "plan": check.plan,
                            "checked_at": check.checked_at,
                            "checked_by_name": check.checked_by_name,
                        }
                        for check in c.checks
                    ],
                }
                for c in completeness[: args.limit]
            ],
        }
    )


# ── product_devices ───────────────────────────────────────────────────


class ProductDevicesInput(ToolInput):
    product_number: str = Field(
        min_length=1,
        max_length=200,
        description="The product number, exactly as Glados shows it.",
    )
    search: str | None = Field(
        default=None,
        max_length=200,
        description="Only devices whose name contains this text, such as Y3 or Lift.",
    )
    only_incomplete: bool = Field(
        default=False,
        description=(
            "Only devices that still miss a plan the product needs or are in no flow sequence."
        ),
    )
    include_archived: bool = Field(
        default=False,
        description="Also archived devices. They have no completeness, since no plan needs them.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="The most devices to return; device_count says how many match.",
    )


class _Lookups:
    """The kinds and the option lists a device refers to by id, resolved to
    the labels the acting user reads."""

    def __init__(self, kinds: list[ProductDeviceKindResult], options: dict[int, str]) -> None:
        self.kinds = {kind.id: kind for kind in kinds}
        self.options = options

    def option(self, option_id: int | None) -> str | None:
        return None if option_id is None else self.options.get(option_id)

    def positions(self, device: ProductDeviceResult) -> dict[int, str]:
        kind = self.kinds.get(device.kind_id)
        return {
            position.id: device.position_labels.get(str(position.id))
            or resolve_label(position.label)
            for position in (kind.positions if kind else [])
        }


def _components(
    components: list[ProductDeviceComponentResult], lookups: _Lookups, positions: dict[int, str]
) -> list[dict[str, Any]]:
    return [
        {
            "role": lookups.option(component.role_id),
            "bought_item_part_number": component.bought_item_part_number,
            "bought_item_article_name": component.bought_item_article_name,
            "eplan_tag": component.eplan_tag,
            "b10d_cycles": component.b10d_cycles,
            "mttfd_years": component.mttfd_years,
            "note": component.note,
            "signals": [
                {
                    "signal_type": signal.signal_type,
                    "meaning": signal.meaning,
                    "confirms_position": positions.get(signal.confirms_position_id)
                    if signal.confirms_position_id is not None
                    else None,
                    "drives_position": positions.get(signal.drives_position_id)
                    if signal.drives_position_id is not None
                    else None,
                    "safety": signal.safety,
                    "address": signal.address,
                    "tag_name": signal.tag_name,
                }
                for signal in component.signals
            ],
        }
        for component in components
    ]


def _parameters(device: ProductDeviceResult, kind: ProductDeviceKindResult | None) -> list[Any]:
    by_id = {str(p.id): p for p in (kind.parameters if kind else [])}
    rows: list[dict[str, Any]] = []
    for parameter_id, value in device.parameters.items():
        parameter = by_id.get(str(parameter_id))
        rows.append(
            {
                "parameter": resolve_label(parameter.label) if parameter else parameter_id,
                "value": value,
                "unit": parameter.unit if parameter else None,
            }
        )
    return rows


def _plan_state(
    state: DeviceCompleteness | None, plans: list[DevicePlan]
) -> tuple[dict[DevicePlan, ProductDeviceCheck], list[DevicePlan], SequenceCoverage | None]:
    """The plan checks of a device by plan, the required plans it still
    lacks and its sequence coverage. A device without a completeness entry
    has nothing checked and nothing reported missing."""
    if state is None:
        return {}, [], None
    checked = {check.plan: check for check in state.checks}
    return checked, [plan for plan in plans if plan not in checked], state.sequence_coverage


def _positions(
    device: ProductDeviceResult, kind: ProductDeviceKindResult | None, labels: dict[int, str]
) -> list[dict[str, Any]]:
    return [
        {
            "position": labels[position.id],
            "takes_value": position.takes_value,
            "unit": position.unit,
            "travel_time_ms": device.travel_times_ms.get(str(position.id)),
        }
        for position in (kind.positions if kind else [])
        if not position.archived
    ]


def _device_row(
    device: ProductDeviceResult,
    lookups: _Lookups,
    names: dict[int, str],
    state: DeviceCompleteness | None,
    plans: list[DevicePlan],
) -> dict[str, Any]:
    checked, missing, coverage = _plan_state(state, plans)
    kind = lookups.kinds.get(device.kind_id)
    labels = lookups.positions(device)
    return {
        "device_id": device.id,
        "name": device.full_name_utf8,
        "name_ascii": device.full_name_ascii,
        "archived": device.archived,
        "kind": resolve_label(kind.label) if kind else None,
        "description": device.description,
        "driving_medium": lookups.option(device.driving_medium_id),
        "safety_relevant": device.safety_relevant,
        "driven_by": names.get(device.driven_by_id) if device.driven_by_id else None,
        "initial_position": labels.get(device.initial_position_id)
        if device.initial_position_id is not None
        else None,
        "initial_position_value": device.initial_position_value,
        "positions": _positions(device, kind, labels),
        "monitoring_time_ms": device.monitoring_time_ms,
        "energy_loss_behaviour": lookups.option(device.energy_loss_behaviour_id),
        "energy_restoration_behaviour": lookups.option(device.energy_restoration_behaviour_id),
        "parameters": _parameters(device, kind),
        "components": _components(device.components, lookups, labels),
        "sequence_coverage": coverage,
        "plans_checked": [
            {
                "plan": check.plan,
                "checked_at": check.checked_at,
                "checked_by_name": check.checked_by_name,
            }
            for check in checked.values()
        ],
        "plans_missing": missing,
    }


def _is_listed(row: dict[str, Any], needle: str, only_incomplete: bool) -> bool:
    if needle and needle not in str(row["name"]).casefold():
        return False
    return not only_incomplete or bool(row["plans_missing"]) or row["sequence_coverage"] == "none"


async def _product_devices(ctx: AgentToolContext, args: ProductDevicesInput) -> ToolOutput:
    product = await _product(ctx, args.product_number)
    devices_use_case = await ctx.use_case(get_product_devices_use_case)
    devices = await devices_use_case.execute(product.id, args.include_archived)
    completeness_use_case = await ctx.use_case(get_product_device_completeness_use_case)
    completeness = {c.device_id: c for c in await completeness_use_case.execute(product.id)}
    kinds_use_case = await ctx.use_case(get_product_device_kinds_use_case)
    options_use_case = await ctx.use_case(get_product_device_options_use_case)
    lookups = _Lookups(
        await kinds_use_case.execute(True),
        {o.id: resolve_label(o.label) for o in await options_use_case.execute(None, True)},
    )
    plans = required_plans(
        electrics=product.contains_electrics,
        pneumatics=product.contains_pneumatics,
        hydraulics=product.contains_hydraulics,
        robotics=product.contains_robotics,
    )
    names = {device.id: device.full_name_utf8 for device in devices}
    needle = (args.search or "").strip().casefold()
    rows = [
        row
        for row in (
            _device_row(device, lookups, names, completeness.get(device.id), plans)
            for device in devices
        )
        if _is_listed(row, needle, args.only_incomplete)
    ]
    return ToolOutput(
        {
            "product_number": product.product_number,
            "plans_required": plans,
            "device_count": len(rows),
            "devices": rows[: args.limit],
        }
    )


# ── renumber_impact ───────────────────────────────────────────────────


class RenumberImpactInput(ToolInput):
    product_number: str = Field(
        min_length=1,
        max_length=200,
        description="The product's current number.",
    )
    new_number: str = Field(
        min_length=1,
        max_length=200,
        description="The number the product would get.",
    )


async def _renumber_impact(ctx: AgentToolContext, args: RenumberImpactInput) -> ToolOutput:
    product = await _product(ctx, args.product_number)
    use_case = await ctx.use_case(get_product_renumber_impact_use_case)
    result = await use_case.execute(product.id, args.new_number)
    return ToolOutput(ProductRenumberImpactResponse.model_validate(result.model_dump()))


WORKSPACE_AGENT_CATALOG = AgentCatalog(
    tools=(
        AgentTool(
            name="project_status",
            title="Project status",
            description=(
                "Where a project stands, by its project number: its status, customer, product, "
                "required delivery dates and production time budget, the unfinished work it "
                "still has (lots, production orders, order lines, demands, quote requests), the "
                "status moves you could make now, and its demand counts by status and order "
                "count."
            ),
            input_model=ProjectStatusInput,
            handler=_project_status,
        ),
        AgentTool(
            name="product_status",
            title="Product status",
            description=(
                "Where a product stands, by its product number: its details, the demand counts "
                "and order count over all projects built on it, and for each live device the "
                "plans outside Glados it is ticked as drawn in (such as the CAD assembly or the "
                "EPLAN plan) and whether a released or draft flow sequence covers it."
            ),
            input_model=ProductStatusInput,
            handler=_product_status,
        ),
        AgentTool(
            name="product_devices",
            title="Product devices",
            description=(
                "The devices of a product, by its product number: each device's name, kind, "
                "driving medium, positions with travel times, initial position, parameters, "
                "components with their bought items and signals, energy behaviour, and what "
                "is still missing on it: the plans outside Glados the product needs (such as "
                "the CAD assembly or the EPLAN plan) it is not ticked as drawn in yet, and "
                "whether a released or draft flow sequence covers it. Use only_incomplete to "
                "find the devices that still need work."
            ),
            input_model=ProductDevicesInput,
            handler=_product_devices,
        ),
        AgentTool(
            name="renumber_impact",
            title="Product renumber impact",
            description=(
                "What giving a product a new number would affect, without changing anything: "
                "how many device names change (with examples of old and new names) and how many "
                "released calculations and checklists and their exported reports still show the "
                "old number. External systems that look the product up by number are affected "
                "too, which Glados cannot count. Use it before suggesting a renumbering."
            ),
            input_model=RenumberImpactInput,
            handler=_renumber_impact,
        ),
        *MEETING_TOOLS,
    ),
)
