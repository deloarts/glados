"""
What the read tier offers AI agents: the global search, the lifecycles of
Glados as the code runs them, and the ready-made prompts that combine the
tools of every module into one task, such as a morning briefing.
"""

from collections.abc import Mapping

from pydantic import Field

from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.adapters.inbound.mcp.tools import AgentPrompt
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import PromptArgument
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.domain.exceptions import NotFoundError
from src.read.adapters.inbound.api.deps import get_global_search_use_case
from src.read.adapters.inbound.api.deps import get_state_machine_catalog_use_case
from src.read.ports.outbound.repositories.global_search_repository import SearchResource

# ── search ───────────────────────────────────────────────────────────


class SearchInput(ToolInput):
    query: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "What to look for: a number (project, product, part, order, lot), a name, an "
            "order code or a word of a description."
        ),
    )
    resources: list[SearchResource] | None = Field(
        default=None,
        min_length=1,
        description="Only these kinds of record; every kind when empty.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="The most hits per kind of record; each kind's total says how many match.",
    )


async def _search(ctx: AgentToolContext, args: SearchInput) -> ToolOutput:
    use_case = await ctx.use_case(get_global_search_use_case)
    result = await use_case.execute(query=args.query, limit=args.limit)
    wanted = set(args.resources) if args.resources else None
    groups = [
        group
        for group in result.groups
        if group.total > 0 and (wanted is None or group.resource in wanted)
    ]
    return ToolOutput({"query": result.query, "groups": groups})


# ── explain_lifecycle ────────────────────────────────────────────────


class ExplainLifecycleInput(ToolInput):
    name: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "The key of one lifecycle, such as lot_status, or its entity, such as Lot. "
            "Leave it empty to list every lifecycle with its key and what it covers."
        ),
    )


async def _explain_lifecycle(ctx: AgentToolContext, args: ExplainLifecycleInput) -> ToolOutput:
    use_case = await ctx.use_case(get_state_machine_catalog_use_case)
    machines = (await use_case.execute()).machines
    if args.name is None:
        return ToolOutput(
            {
                "lifecycles": [
                    {
                        "key": m.key,
                        "entity": m.entity,
                        "kind": m.kind,
                        "description": m.description,
                    }
                    for m in machines
                ]
            }
        )
    wanted = args.name.strip().casefold()
    for machine in machines:
        if wanted in (machine.key.casefold(), machine.entity.casefold()):
            return ToolOutput(machine)
    known = ", ".join(m.key for m in machines)
    raise NotFoundError(f"No lifecycle {args.name!r}. Known lifecycles: {known}.")


# ── Prompts ──────────────────────────────────────────────────────────

_DRAFTS_WAIT = (
    "Anything a draft tool creates is only a draft: a person has to review and commit it in "
    "the Glados web app before anything is ordered, sent or scheduled."
)
_READ_ONLY = f"This task only reads, so create no drafts. {_DRAFTS_WAIT}"


def _morning_briefing(_arguments: Mapping[str, str]) -> str:
    return (
        "Give me my morning briefing for Glados. Call my_briefing for my own work, "
        "my_notifications for what happened since I last looked, and list_planning_exceptions "
        "for the planning problems. Then summarise, most urgent first, what needs a decision "
        "from me today, naming each record by its number, and say in one line what you would "
        "do about each. Leave out what needs nothing from me. "
        f"{_READ_ONLY}"
    )


def _project_report(arguments: Mapping[str, str]) -> str:
    project = arguments["project_number"]
    return (
        f"Write a status report for project {project}, ready to paste into an e-mail to "
        f"colleagues. Call project_status for project {project}, and demand_coverage and "
        "schedule where you need detail on open demands or on production dates. Cover the "
        "overall state, what is done, what is open, the dates at risk with their cause, and "
        "what is waiting for a decision. Use plain sentences and short paragraphs, name parts, "
        "lots and orders by their numbers, and give no figure the tools did not return. "
        f"{_READ_ONLY}"
    )


def _why_late(arguments: Mapping[str, str]) -> str:
    lot = arguments["lot_number"]
    return (
        f"Explain why production lot {lot} is late. Start with explain_lot for lot {lot}, then "
        "follow the cause back step by step: use schedule to see which machine work holds it "
        "up and demand_coverage to see which bought or made parts are missing or arrive late. "
        "Keep going until you reach the root cause, such as a supplier date, a missing order, "
        "a machine that is fully booked or a lot without an approved source. Give the chain "
        "from the lot to that cause, each link with its record number and date, and end with "
        "what would bring the lot back on time. "
        f"{_READ_ONLY}"
    )


def _procurement_review(arguments: Mapping[str, str]) -> str:
    project = (arguments.get("project_number") or "").strip()
    scope = f"of project {project}" if project else "of every open project"
    return (
        f"Review the open bought demands {scope} that no order or stock covers yet. Use "
        "demand_coverage to find them, item for part details, orders to check for an order "
        "that is already open, and compare_offers where several suppliers could deliver. "
        "Group what is uncovered by supplier, and for each supplier list part number, "
        "quantity and the date it is needed by. Then offer to create draft purchase orders "
        "with draft_purchase_order, or draft quote requests with draft_quote_request where "
        "no usable offer exists, and wait for my answer: never create a draft I did not ask "
        f"for. {_DRAFTS_WAIT}"
    )


def _weekly_kpis(_arguments: Mapping[str, str]) -> str:
    return (
        "Compare the production KPIs of last week with the week before. Work out both weeks "
        "as Monday to Sunday from today's date; if you do not know today's date, ask me. Call "
        "production_kpis once for each week with the summary view, and once for both weeks "
        "together with the weekly and late_lots views. Show the two weeks side by side, say "
        "which KPIs moved noticeably and in which direction, and for every KPI that got "
        "worse give the likely cause from the late lots and their delay reasons. "
        f"{_READ_ONLY}"
    )


READ_TIER_AGENT_CATALOG = AgentCatalog(
    tools=(
        AgentTool(
            name="search",
            title="Search",
            description=(
                "Search Glados for a number, name or word across products, projects, bought, "
                "made and source items, orders, production lots and orders, calculations and "
                "checklists. Returns the ids and public ids the other tools take, best match "
                "first, grouped by kind."
            ),
            input_model=SearchInput,
            handler=_search,
        ),
        AgentTool(
            name="explain_lifecycle",
            title="Explain a lifecycle",
            description=(
                "How a status in Glados comes about: one lifecycle's states, the rules that "
                "derive its status, the actions people can take with their permissions, and "
                "the transitions with what they cause elsewhere. Without a name, lists the "
                "lifecycles."
            ),
            input_model=ExplainLifecycleInput,
            handler=_explain_lifecycle,
        ),
    ),
    prompts=(
        AgentPrompt(
            name="morning-briefing",
            title="Morning briefing",
            description="What needs a decision from you today, from your work, notifications "
            "and the planning exceptions.",
            arguments=(),
            render=_morning_briefing,
        ),
        AgentPrompt(
            name="project-report",
            title="Project report",
            description="A status report of one project, ready to paste into an e-mail.",
            arguments=(
                PromptArgument(
                    name="project_number", description="The project number, such as P-24017."
                ),
            ),
            render=_project_report,
        ),
        AgentPrompt(
            name="why-late",
            title="Why is this lot late?",
            description="Walks a late production lot back to the cause of its delay.",
            arguments=(
                PromptArgument(name="lot_number", description="The number of the production lot."),
            ),
            render=_why_late,
        ),
        AgentPrompt(
            name="procurement-review",
            title="Procurement review",
            description="Open bought demands without coverage, grouped by supplier, with an "
            "offer to draft the purchase orders.",
            arguments=(
                PromptArgument(
                    name="project_number",
                    description="Only this project; every open project when empty.",
                    required=False,
                ),
            ),
            render=_procurement_review,
        ),
        AgentPrompt(
            name="weekly-kpis",
            title="Weekly KPIs",
            description="The production KPIs of last week compared with the week before.",
            arguments=(),
            render=_weekly_kpis,
        ),
    ),
)
