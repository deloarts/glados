"""
The tags meetings carry, offered while a tag is typed. They are suggested
across all meetings rather than per owner, since a tag such as "Milestone"
means the same in every project and product.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.application.dto.meeting_dto import MeetingTagQuery
from src.modules.workspace.application.dto.meeting_dto import MeetingTagSuggestionResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTagSuggestionsResult
from src.modules.workspace.application.use_cases.meeting._support import MeetingUseCase
from src.modules.workspace.domain.services.meeting_tags import ranked_tags


class GetMeetingTagSuggestions(MeetingUseCase):
    """The tags the meetings not deleted carry, invalid ones included, that
    contain the query, most used first."""

    async def execute(self, actor: User, query: MeetingTagQuery) -> MeetingTagSuggestionsResult:
        uses = await self._meetings.get_tag_uses()
        return MeetingTagSuggestionsResult(
            suggestions=[
                MeetingTagSuggestionResult(name=use.name, count=use.count)
                for use in ranked_tags(uses, query.query, max(1, min(query.limit, 100)))
            ]
        )
