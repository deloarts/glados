"""
The scopes the cards of an owner use: suggestions ranked by use with the
existing scope a new one nearly repeats, and renaming a scope across the
owner's meetings. A project's suggestions draw on its product and the
product's other projects too; a product's on its own meetings and those of
its projects, which is also what a rename of a product's scope reaches.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.workspace.application.dto.meeting_dto import MeetingScopeQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingScopeSuggestionResult
from src.modules.workspace.application.dto.meeting_dto import MeetingScopeSuggestionsResult
from src.modules.workspace.application.dto.meeting_dto import RenameMeetingScopeCommand
from src.modules.workspace.application.dto.meeting_dto import RenameMeetingScopeResult
from src.modules.workspace.application.use_cases.meeting._support import MeetingUseCase
from src.modules.workspace.application.use_cases.meeting._support import owner_meetings_scope
from src.modules.workspace.application.use_cases.meeting._support import save_card_content
from src.modules.workspace.domain.services.meeting_rules import SCOPE_MAX
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.services.meeting_scopes import near_duplicate
from src.modules.workspace.domain.services.meeting_scopes import ranked
from src.shared_kernel.domain.services.clock import now_utc


class _ScopeUseCase(MeetingUseCase):
    async def _meeting_ids(
        self, project_id: int | None, product_id: int | None, *, family: bool
    ) -> list[int]:
        """The ids of the meetings, invalid ones included, a scope action
        covers. `family` widens a project to its product and the product's
        projects."""
        if family and project_id is not None:
            project = await self._ports.projects.get_by_id(project_id)
            if project is not None and not project.deleted and project.product_id is not None:
                project_id, product_id = None, project.product_id
        project_ids, product_ids = await owner_meetings_scope(
            self._ports, project_id, product_id, with_projects=True
        )
        rows = await self._meetings.list_rows(
            project_ids=project_ids,
            product_ids=product_ids,
            include_invalid=True,
            today=now_utc().date(),
        )
        return [row.meeting.id for row in rows]


class GetMeetingScopeSuggestions(_ScopeUseCase):
    async def execute(self, actor: User, query: MeetingScopeQuery) -> MeetingScopeSuggestionsResult:
        meeting_ids = await self._meeting_ids(query.project_id, query.product_id, family=True)
        uses = await self._cards.get_scope_uses(meeting_ids)
        return MeetingScopeSuggestionsResult(
            suggestions=[
                MeetingScopeSuggestionResult(scope=use.scope, icon=use.icon, count=use.count)
                for use in ranked(uses, query.query, max(1, min(query.limit, 100)))
            ],
            near_duplicate=near_duplicate(query.query, uses) if query.query else None,
        )


class RenameMeetingScope(_ScopeUseCase):
    """Renames the scope on every card of the owner's valid meetings that
    carries it exactly. Each renamed card gets a revision of its own."""

    async def execute(
        self, actor: User, cmd: RenameMeetingScopeCommand
    ) -> RenameMeetingScopeResult:
        MeetingRules.assert_can_write(actor)
        source = MeetingRules.required_text(cmd.from_scope, "scope", SCOPE_MAX)
        target = MeetingRules.required_text(cmd.to_scope, "new scope", SCOPE_MAX)
        if source == target:
            return RenameMeetingScopeResult(renamed=0)
        meeting_ids = await self._meeting_ids(cmd.project_id, cmd.product_id, family=False)
        valid = [
            meeting_id
            for meeting_id in meeting_ids
            if (meeting := await self._meetings.get_by_id(meeting_id)) is not None
            and not meeting.invalid
        ]
        cards = await self._cards.get_cards_with_scope(valid, source)
        for card in cards:
            await self._cards.lock_card(card.id)
            await save_card_content(
                self._ports,
                actor,
                card,
                scope=target,
                scope_icon=card.scope_icon,
                body=card.body,
                internal=card.internal,
                always_new_revision=True,
            )
        await self._uow.commit()
        log.info(f"Renamed scope {source!r} to {target!r} on {len(cards)} card(s).")
        return RenameMeetingScopeResult(renamed=len(cards))
