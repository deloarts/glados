"""
The pure rules of meeting tags: how a list of tags is normalised, which
lists are refused, and how the tags in use are ranked for suggestions.
"""

import pytest

from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.services.meeting_tags import TAG_MAX
from src.modules.workspace.domain.services.meeting_tags import TAGS_MAX
from src.modules.workspace.domain.services.meeting_tags import TagUse
from src.modules.workspace.domain.services.meeting_tags import normalise_tags
from src.modules.workspace.domain.services.meeting_tags import ranked_tags


class TestNormaliseTags:
    def test_trims_collapses_and_drops_empty_tags_in_the_given_order(self) -> None:
        tags = normalise_tags(["  Risk ", "", "Factory \t  acceptance", "   ", "Milestone"])

        assert tags == ["Risk", "Factory acceptance", "Milestone"]

    def test_a_repeat_in_another_case_keeps_the_first_spelling(self) -> None:
        tags = normalise_tags(["Milestone", "risk", "MILESTONE", " milestone ", "Risk"])

        assert tags == ["Milestone", "risk"]

    def test_no_tags_is_fine(self) -> None:
        assert normalise_tags([]) == []

    def test_a_tag_over_the_limit_is_refused_after_trimming(self) -> None:
        assert normalise_tags([f"  {'x' * TAG_MAX}  "]) == ["x" * TAG_MAX]
        with pytest.raises(MeetingInvalidInputError, match="at most 40 characters"):
            normalise_tags(["x" * (TAG_MAX + 1)])

    def test_more_tags_than_the_limit_are_refused_once_repeats_are_gone(self) -> None:
        tags = [f"Tag {i}" for i in range(TAGS_MAX)]

        assert normalise_tags([*tags, "tag 0", ""]) == tags
        with pytest.raises(MeetingInvalidInputError, match="at most 10 tags"):
            normalise_tags([*tags, "One more"])


class TestRankedTags:
    def test_spellings_count_as_one_under_the_most_used_one(self) -> None:
        uses = [TagUse("milestone", 1), TagUse("Milestone", 2), TagUse("Risk", 1)]

        assert ranked_tags(uses, None, 20) == [TagUse("Milestone", 3), TagUse("Risk", 1)]

    def test_equal_counts_rank_by_name_and_the_query_narrows(self) -> None:
        uses = [TagUse("Risk", 1), TagUse("Acceptance", 1), TagUse("Schedule", 2)]

        assert [u.name for u in ranked_tags(uses, None, 20)] == ["Schedule", "Acceptance", "Risk"]
        assert [u.name for u in ranked_tags(uses, " ACC ", 20)] == ["Acceptance"]
        assert [u.name for u in ranked_tags(uses, "s", 20)] == ["Schedule", "Risk"]

    def test_the_limit_caps_the_list(self) -> None:
        uses = [TagUse(f"Tag {i}", i) for i in range(5)]

        assert [u.name for u in ranked_tags(uses, None, 2)] == ["Tag 4", "Tag 3"]
