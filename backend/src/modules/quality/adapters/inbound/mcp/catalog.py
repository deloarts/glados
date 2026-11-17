"""
What Quality offers AI agents: the production KPIs, the distribution journal
of a report, the controlled documents (checklists, calculations and
sequences) of a project or product with their release and lock state, and
the content of one sequence or calculation (see content_tools.py).

Each tool builds its use case through the factory of the web route it
mirrors and builds the use case's query through that route's own parameter
model, so a tool validates and filters exactly as the route does.
"""

from datetime import date
from typing import Any
from typing import Literal
from typing import cast
from uuid import UUID

from pydantic import Field

from src.modules.platform.adapters.inbound.mcp.tools import AgentCatalog
from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.quality.adapters.inbound.api.deps.calculations import get_calculations_use_case
from src.modules.quality.adapters.inbound.api.deps.checklists import get_checklists_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_report_journal_use_case
from src.modules.quality.adapters.inbound.api.deps.production_kpis import (
    get_compute_production_kpis_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.sequences import get_sequences_use_case
from src.modules.quality.adapters.inbound.api.schemas.calculation_schema import (
    CalculationFilterParams,
)
from src.modules.quality.adapters.inbound.api.schemas.checklist_schema import ChecklistFilterParams
from src.modules.quality.adapters.inbound.api.schemas.production_kpi_schema import (
    ProductionKpiFilterParams,
)
from src.modules.quality.adapters.inbound.api.schemas.sequence_schema import SequenceFilterParams
from src.modules.quality.adapters.inbound.mcp.content_tools import CALCULATION_TOOL
from src.modules.quality.adapters.inbound.mcp.content_tools import SEQUENCE_TOOL
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculations
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklists
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequences
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

KpiView = Literal[
    "summary",
    "weekly",
    "utilization",
    "estimate_accuracy",
    "waiting_time",
    "late_lots",
    "quality_by_item",
    "scrap_by_reason",
    "rejected_per_supplier",
]
DocumentKind = Literal["checklists", "calculations", "sequences"]

# ── production_kpis ──────────────────────────────────────────────────


class ProductionKpisInput(ToolInput):
    date_from: date = Field(description="First day of the period, as YYYY-MM-DD.")
    date_to: date = Field(
        description="Last day of the period, as YYYY-MM-DD, not before date_from."
    )
    views: list[KpiView] = Field(
        default_factory=lambda: list[KpiView](["summary"]),
        min_length=1,
        description=(
            "Which KPI views to compute. summary holds schedule adherence, on-time delivery, "
            "throughput time, first pass yield, scrap and rework ratios, utilization, "
            "availability and OEE. weekly holds adherence and on-time delivery per ISO week. "
            "The others are tables: utilization per machine, estimate_accuracy per fabrication "
            "method, waiting_time per position kind, late_lots with the reason for each delay, "
            "quality_by_item, scrap_by_reason and rejected_per_supplier."
        ),
    )
    machine_id: int | None = Field(
        default=None, description="Only this production machine. Not together with a pool."
    )
    machine_pool_id: int | None = Field(
        default=None, description="Only the machines of this pool. Not together with a machine."
    )
    project_id: int | None = Field(
        default=None, description="Only this project, by its id (find it with search)."
    )
    customer_id: int | None = Field(
        default=None, description="Only the projects of this customer, by its id."
    )
    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description="The most rows each table view returns; its total says how many exist.",
    )


async def _production_kpis(ctx: AgentToolContext, args: ProductionKpisInput) -> ToolOutput:
    kpi_filter = ProductionKpiFilterParams(
        date_from=args.date_from,
        date_to=args.date_to,
        machine_id=args.machine_id,
        machine_pool_id=args.machine_pool_id,
        project_id=args.project_id,
        customer_id=args.customer_id,
    ).to_filter()
    use_case = await ctx.use_case(get_compute_production_kpis_use_case)
    data: dict[str, Any] = {"date_from": args.date_from, "date_to": args.date_to}
    for view in dict.fromkeys(args.views):
        result = await getattr(use_case, view)(kpi_filter)
        rows = getattr(result, "rows", None)
        data[view] = result if rows is None else {"total": len(rows), "rows": rows[: args.limit]}
    return ToolOutput(data)


# ── report_journal ───────────────────────────────────────────────────


class ReportJournalInput(ToolInput):
    document: UploadedPrintDocument = Field(
        description=(
            "The kind of report: calculation_report for a calculation, checklist_report for a "
            "checklist, inspection_report for a production lot."
        )
    )
    root_public_id: UUID = Field(
        description=(
            "The public id of the calculation, checklist or production lot the report is of, "
            "as search or controlled_documents return it."
        )
    )
    limit: int = Field(
        default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="The most entries to return."
    )


async def _report_journal(ctx: AgentToolContext, args: ReportJournalInput) -> ToolOutput:
    use_case = await ctx.use_case(get_report_journal_use_case)
    entries = await use_case.execute(ctx.actor, args.document.value, args.root_public_id)
    return ToolOutput({"total": len(entries), "items": entries[: args.limit]})


# ── controlled_documents ─────────────────────────────────────────────


class ControlledDocumentsInput(ToolInput):
    project_id: int | None = Field(
        default=None,
        description="Only the documents of this project, by its id (find it with search).",
    )
    product_id: int | None = Field(
        default=None,
        description="Only the documents of this product, by its id (find it with search).",
    )
    include_product_projects: bool = Field(
        default=False,
        description=(
            "With product_id, also the checklists and calculations of the product's projects."
        ),
    )
    kinds: list[DocumentKind] = Field(
        default_factory=lambda: list[DocumentKind](["checklists", "calculations", "sequences"]),
        min_length=1,
        description=(
            "Which kinds of document to list. Sequences belong to a product only, so they are "
            "left out when project_id is given."
        ),
    )
    released: bool | None = Field(
        default=None,
        description="True for released documents only, false for unreleased ones, empty for both.",
    )
    search: str | None = Field(
        default=None,
        max_length=200,
        description="Part of the title, name or document number.",
    )
    all_revisions: bool = Field(
        default=False,
        description="Also earlier revisions, not only the latest revision of each document.",
    )
    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description="The most documents per kind; each kind's total says how many exist.",
    )


async def _controlled_documents(
    ctx: AgentToolContext, args: ControlledDocumentsInput
) -> ToolOutput:
    by_product = args.product_id if not args.include_product_projects else None
    related_product = args.product_id if args.include_product_projects else None
    data: dict[str, Any] = {}

    if "checklists" in args.kinds:
        checklists = cast(GetChecklists, await ctx.use_case(get_checklists_use_case))
        params = ChecklistFilterParams(
            limit=args.limit,
            project_id=args.project_id,
            product_id=by_product,
            related_product_id=related_product,
            released=args.released,
            search=args.search,
            all_revisions=args.all_revisions,
        )
        page = await checklists.execute(actor=ctx.actor, query=params.to_query())
        data["checklists"] = {"total": page.total, "items": page.items}

    if "calculations" in args.kinds:
        calculations = cast(GetCalculations, await ctx.use_case(get_calculations_use_case))
        params_c = CalculationFilterParams(
            limit=args.limit,
            project_id=args.project_id,
            product_id=by_product,
            related_product_id=related_product,
            released=args.released,
            search=args.search,
            all_revisions=args.all_revisions,
        )
        page_c = await calculations.execute(actor=ctx.actor, query=params_c.to_query())
        # The results of a calculation are the tool's own figures, which can
        # be long and may hold costs; the agent reads the release state.
        data["calculations"] = {
            "total": page_c.total,
            "items": [item.model_dump(exclude={"results"}) for item in page_c.items],
        }

    if "sequences" in args.kinds and args.project_id is None:
        sequences = cast(GetSequences, await ctx.use_case(get_sequences_use_case))
        params_s = SequenceFilterParams(
            limit=args.limit,
            product_id=args.product_id,
            released=args.released,
            search=args.search,
            all_revisions=args.all_revisions,
        )
        page_s = await sequences.execute(actor=ctx.actor, query=params_s.to_query())
        data["sequences"] = {"total": page_s.total, "items": page_s.items}

    return ToolOutput(data)


QUALITY_AGENT_CATALOG = AgentCatalog(
    tools=(
        AgentTool(
            name="production_kpis",
            title="Production KPIs",
            description=(
                "Production KPIs over a period, computed live: schedule adherence, on-time "
                "delivery, throughput time, utilization, availability, first pass yield, scrap "
                "and rework, OEE, and on request the weekly trend and the tables behind them. "
                "Narrow it to a machine, a machine pool, a project or a customer."
            ),
            input_model=ProductionKpisInput,
            handler=_production_kpis,
        ),
        AgentTool(
            name="report_journal",
            title="Report journal",
            description=(
                "Where the PDF reports of a calculation, checklist or production lot went: "
                "every download and print of any revision, newest first, with revision, "
                "language, size and hash."
            ),
            input_model=ReportJournalInput,
            handler=_report_journal,
        ),
        AgentTool(
            name="controlled_documents",
            title="Controlled documents",
            description=(
                "The checklists, calculations and sequences of a project or product, newest "
                "change first, each with document number, revision, whether it is released, "
                "superseded or marked invalid, and who holds its edit lock. Checklists add "
                "their verdict and progress. Another user's personal documents stay hidden."
            ),
            input_model=ControlledDocumentsInput,
            handler=_controlled_documents,
        ),
        SEQUENCE_TOOL,
        CALCULATION_TOOL,
    ),
)
