"""
The meeting tools of Workspace. `meetings` finds the meetings of a project
or a product without their notes or their attendees, so an agent can tell
which meeting a record of notes belongs to. `draft_meeting_notes` submits
notes the agent read from a record the user gave it, such as handwritten
notes or a photo of a notebook page, as a draft that waits for the user:
they match its names to people, adjust it and apply it in Glados. The tool
never writes a meeting, never notifies anybody and never sends notes.
"""

from datetime import date
from datetime import time
from typing import Self

from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from src.modules.platform.adapters.inbound.mcp.tools import AgentTool
from src.modules.platform.adapters.inbound.mcp.tools import AgentToolContext
from src.modules.platform.adapters.inbound.mcp.tools import DraftToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolInput
from src.modules.platform.adapters.inbound.mcp.tools import ToolKind
from src.modules.platform.adapters.inbound.mcp.tools import ToolOutput
from src.modules.platform.adapters.inbound.mcp.tools import ref
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.inbound.api.deps.meetings import (
    get_create_meeting_notes_draft_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.meetings import get_list_meetings_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_product_by_number_use_case
from src.modules.workspace.adapters.inbound.api.deps.products import get_project_by_number_use_case
from src.modules.workspace.application.dto.meeting_dto import MeetingListQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingListRowResult
from src.modules.workspace.application.dto.meeting_notes_draft_dto import (
    CreateMeetingNotesDraftCommand,
)
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftAttendeeInput
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftCardInput
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftNewMeetingInput
from src.modules.workspace.application.dto.meeting_notes_draft_dto import DraftTodoInput
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

_OWNER_HINT = "Name exactly one of project_number and product_number, as Glados shows them."


class _OwnerInput(ToolInput):
    project_number: str | None = Field(
        default=None, min_length=1, max_length=200, description="The project's number."
    )
    product_number: str | None = Field(
        default=None, min_length=1, max_length=200, description="The product's number."
    )

    @model_validator(mode="after")
    def _one_owner(self) -> Self:
        if (self.project_number is None) == (self.product_number is None):
            raise ValueError(_OWNER_HINT)
        return self


async def _owner_ids(
    ctx: AgentToolContext, project_number: str | None, product_number: str | None
) -> tuple[int | None, int | None]:
    if project_number is not None:
        use_case = await ctx.use_case(get_project_by_number_use_case)
        return (await use_case.execute(number=project_number)).id, None
    assert product_number is not None
    use_case_p = await ctx.use_case(get_product_by_number_use_case)
    return None, (await use_case_p.execute(product_number=product_number)).id


async def _meeting_rows(
    ctx: AgentToolContext, project_id: int | None, product_id: int | None
) -> list[MeetingListRowResult]:
    use_case = await ctx.use_case(get_list_meetings_use_case)
    query = MeetingListQuery(project_id=project_id, product_id=product_id, include_invalid=False)
    return await use_case.execute(ctx.actor, query)


# ── meetings ──────────────────────────────────────────────────────────


class MeetingsInput(_OwnerInput):
    starts_from: date | None = Field(
        default=None, description="Only meetings that start on or after this day."
    )
    starts_until: date | None = Field(
        default=None, description="Only meetings that start on or before this day."
    )
    limit: int = Field(default=20, ge=1, le=100, description="The most meetings to return.")


async def _meetings(ctx: AgentToolContext, args: MeetingsInput) -> ToolOutput:
    project_id, product_id = await _owner_ids(ctx, args.project_number, args.product_number)
    rows = await _meeting_rows(ctx, project_id, product_id)
    if args.starts_from is not None:
        rows = [r for r in rows if r.starts_at.date() >= args.starts_from]
    if args.starts_until is not None:
        rows = [r for r in rows if r.starts_at.date() <= args.starts_until]
    return ToolOutput(
        {
            "total": len(rows),
            "items": [
                {
                    "meeting_number": r.meeting_number,
                    "name": r.name,
                    "owner_number": r.owner.number,
                    "starts_at": r.starts_at,
                    "ends_at": r.ends_at,
                    "location": r.location,
                    "tags": r.tags,
                    "card_count": len(r.scopes),
                    "open_todo_count": r.open_todo_count,
                }
                for r in rows[: args.limit]
            ],
        }
    )


# ── draft_meeting_notes ───────────────────────────────────────────────


class DraftAttendeeArg(ToolInput):
    name: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "The person exactly as the notes name them, with the company if the notes give "
            "it, such as 'Hans M. (Müller GmbH)'. Never guess a full name."
        ),
    )
    status: MeetingAttendanceStatus = Field(
        default=MeetingAttendanceStatus.PRESENT,
        description="present, excused, or distribution_only for someone who only gets the notes.",
    )
    email: str | None = Field(
        default=None, max_length=320, description="Only if the notes carry the address."
    )


class DraftTodoArg(ToolInput):
    title: str = Field(min_length=1, max_length=300, description="What is to be done.")
    note: str | None = Field(default=None, max_length=4000, description="Details, if any.")
    due_date: date | None = Field(default=None, description="Only if the notes give a date.")
    owners: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Who does it, each exactly as the notes name them.",
    )


class DraftCardArg(ToolInput):
    scope: str | None = Field(
        default=None,
        max_length=80,
        description="The topic of the card, a few words, such as 'Electrical cabinet'.",
    )
    scope_icon: MeetingScopeIcon | None = Field(
        default=None, description="The icon that fits the topic, if one does."
    )
    body: str = Field(
        default="",
        max_length=100_000,
        description=(
            "What was said, in Markdown: paragraphs, ### headings, **bold**, *italic*, "
            "- and 1. lists two levels deep, links. Other syntax shows as plain text. Keep the "
            "language of the notes."
        ),
    )
    internal: bool = Field(
        default=False, description="True for points that must not go to people outside."
    )
    decisions: list[str] = Field(
        default_factory=list, max_length=50, description="What was decided, one per entry."
    )
    todos: list[DraftTodoArg] = Field(
        default_factory=list, max_length=50, description="What is to be done, by whom and when."
    )
    review_note: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "For the reviewer only, never written to the meeting: what you could not read or "
            "had to guess on this card."
        ),
    )


class DraftMeetingNotesInput(DraftToolInput, _OwnerInput):
    meeting_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "The meeting of the project or product to add the notes to, as the meetings tool "
            "shows it. Leave it out to propose a new meeting and give new_meeting_name, "
            "new_meeting_starts_at and new_meeting_ends_at."
        ),
    )
    new_meeting_name: str | None = Field(
        default=None, min_length=1, max_length=200, description="The new meeting's title."
    )
    new_meeting_starts_at: AwareDatetime | None = Field(
        default=None, description="With its time zone, such as 2026-11-10T09:00:00+01:00."
    )
    new_meeting_ends_at: AwareDatetime | None = Field(
        default=None, description="With its time zone. Without it the meeting ends as it starts."
    )
    new_meeting_location: str | None = Field(
        default=None, max_length=200, description="Where the new meeting took place."
    )
    new_meeting_tags: list[str] = Field(
        default_factory=list, max_length=10, description="Short labels, only if the user asks."
    )
    attendees: list[DraftAttendeeArg] = Field(
        default_factory=list,
        max_length=100,
        description="Who attended, was excused or only gets the notes, as the notes list them.",
    )
    cards: list[DraftCardArg] = Field(
        min_length=1, max_length=100, description="The notes, one card per topic, in order."
    )
    next_meeting_date: date | None = Field(
        default=None, description="The next meeting's day, if the notes agree one."
    )
    next_meeting_time: time | None = Field(
        default=None, description="Its local start time, only with next_meeting_date."
    )
    next_meeting_location: str | None = Field(
        default=None, max_length=200, description="Where the next meeting takes place."
    )
    review_note: str | None = Field(
        default=None,
        max_length=2000,
        description="For the reviewer only: anything about the notes as a whole.",
    )


async def _draft_meeting_notes(ctx: AgentToolContext, args: DraftMeetingNotesInput) -> ToolOutput:
    project_id, product_id = await _owner_ids(ctx, args.project_number, args.product_number)
    meeting_id: int | None = None
    new_meeting: DraftNewMeetingInput | None = None
    if args.meeting_number is not None:
        wanted = args.meeting_number.strip().casefold()
        found = [
            r
            for r in await _meeting_rows(ctx, project_id, product_id)
            if r.meeting_number.casefold() == wanted
        ]
        if not found:
            raise InvalidInputError(
                f"No valid meeting {args.meeting_number} of this project or product. "
                "Use the meetings tool to find it."
            )
        meeting_id, project_id, product_id = found[0].id, None, None
    else:
        if args.new_meeting_name is None or args.new_meeting_starts_at is None:
            raise InvalidInputError(
                "Without a meeting_number, give new_meeting_name and new_meeting_starts_at."
            )
        new_meeting = DraftNewMeetingInput(
            name=args.new_meeting_name,
            starts_at=args.new_meeting_starts_at,
            ends_at=args.new_meeting_ends_at or args.new_meeting_starts_at,
            location=args.new_meeting_location,
            tags=args.new_meeting_tags,
        )
    cmd = CreateMeetingNotesDraftCommand(
        meeting_id=meeting_id,
        project_id=project_id,
        product_id=product_id,
        new_meeting=new_meeting,
        attendees=[
            DraftAttendeeInput(name=a.name, status=a.status, email=a.email) for a in args.attendees
        ],
        cards=[
            DraftCardInput(
                scope=c.scope,
                scope_icon=c.scope_icon,
                body=c.body,
                internal=c.internal,
                decisions=c.decisions,
                todos=[
                    DraftTodoInput(title=t.title, note=t.note, due_date=t.due_date, owners=t.owners)
                    for t in c.todos
                ],
                review_note=c.review_note,
            )
            for c in args.cards
        ],
        next_meeting_date=args.next_meeting_date,
        next_meeting_time=args.next_meeting_time,
        next_meeting_location=args.next_meeting_location,
        review_note=args.review_note,
        token_name=ctx.principal.token_name,
    )
    use_case = await ctx.use_case(get_create_meeting_notes_draft_use_case)
    draft = await use_case.execute(ctx.actor, cmd)
    return ToolOutput(
        {
            "draft": {
                "id": draft.id,
                "meeting_number": draft.meeting_number,
                "owner_number": draft.owner_number,
                "name": draft.name,
                "card_count": draft.card_count,
                "decision_count": draft.decision_count,
                "todo_count": draft.todo_count,
            },
            "review_path": f"/meeting-notes-drafts/{draft.id}",
            "next_step": (
                "The notes are a draft that only the user sees. They review it in Glados, "
                "match the names to people and apply it; until then no meeting changes and "
                "nobody is notified."
            ),
        },
        created_refs=[ref("meeting_notes_draft", draft.public_id)],
    )


MEETING_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="meetings",
        title="Meetings",
        description=(
            "The valid meetings of a project or a product, latest start first, with number, "
            "name, times, location, tags and how many cards and open todos each has. A "
            "product's list includes the meetings of its projects. Use it to find the meeting "
            "a record of notes belongs to; it carries no notes and no attendees."
        ),
        input_model=MeetingsInput,
        handler=_meetings,
    ),
    AgentTool(
        name="draft_meeting_notes",
        title="Draft meeting notes",
        description=(
            "Submits notes of a meeting, read from what the user gave you such as handwritten "
            "notes or a photo, as a draft for the user to review in Glados. It adds to an "
            "existing meeting of the project or product (meeting_number) or proposes a new "
            "one. Write people exactly as the notes name them; the user matches them to "
            "users and contacts. Put what you could not read or had to guess into "
            "review_note rather than the text. Nothing changes and nobody is notified until "
            "the user applies the draft."
        ),
        input_model=DraftMeetingNotesInput,
        handler=_draft_meeting_notes,
        kind=ToolKind.DRAFT,
        requires=(Permission.WRITE_MEETINGS,),
    ),
)
