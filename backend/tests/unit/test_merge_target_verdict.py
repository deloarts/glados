"""
A catalogue item may take a merge while it is active and not archived; one
the merged item had replaced may too, and the merge makes it active again.
The bought and made merge asserts refuse exactly what the verdict refuses.
"""

from typing import Any

import pytest

from src.modules.catalogue.domain.errors import BoughtItemInactiveError
from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.catalogue_item_status import MergeTargetRefusal
from src.modules.catalogue.domain.policies.catalogue_item_status import MergeTargetVerdict
from src.modules.catalogue.domain.policies.catalogue_item_status import merge_target_verdict
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus

SOURCE_ID = 7

CASES = [
    # archived, status, successor, expected verdict
    (False, BoughtItemCatalogueStatus.ACTIVE, None, MergeTargetVerdict(None, reactivates=False)),
    (
        True,
        BoughtItemCatalogueStatus.ACTIVE,
        None,
        MergeTargetVerdict(MergeTargetRefusal.ARCHIVED, reactivates=False),
    ),
    (
        False,
        BoughtItemCatalogueStatus.INACTIVE,
        None,
        MergeTargetVerdict(MergeTargetRefusal.NOT_ACTIVE, reactivates=False),
    ),
    (
        False,
        BoughtItemCatalogueStatus.REPLACED,
        SOURCE_ID,
        MergeTargetVerdict(None, reactivates=True),
    ),
    (
        False,
        BoughtItemCatalogueStatus.REPLACED,
        99,
        MergeTargetVerdict(MergeTargetRefusal.NOT_ACTIVE, reactivates=False),
    ),
    (
        True,
        BoughtItemCatalogueStatus.REPLACED,
        SOURCE_ID,
        MergeTargetVerdict(MergeTargetRefusal.ARCHIVED, reactivates=False),
    ),
]


@pytest.mark.parametrize(("archived", "status", "successor", "expected"), CASES)
def test_merge_target_verdict(
    archived: bool,
    status: BoughtItemCatalogueStatus,
    successor: int | None,
    expected: MergeTargetVerdict,
) -> None:
    verdict = merge_target_verdict(
        archived=archived, status=status, successor_item_id=successor, source_id=SOURCE_ID
    )

    assert verdict == expected


class _Item:
    """The fields the merge assert reads."""

    def __init__(
        self, id: int, archived: bool, status: BoughtItemCatalogueStatus, successor: int | None
    ) -> None:
        self.id = id
        self.archived = archived
        self.status = status
        self.successor_item_id = successor
        self.article_name = "Item"


@pytest.mark.parametrize(
    ("rules", "error"),
    [
        (BoughtItemCatalogueRules, BoughtItemInactiveError),
        (MadeItemCatalogueRules, MadeItemInactiveError),
    ],
)
@pytest.mark.parametrize(("archived", "status", "successor", "expected"), CASES)
def test_the_merge_assert_follows_the_verdict(
    rules: Any,
    error: type[Exception],
    archived: bool,
    status: BoughtItemCatalogueStatus,
    successor: int | None,
    expected: MergeTargetVerdict,
) -> None:
    target = _Item(1, archived, status, successor)
    source = _Item(SOURCE_ID, False, BoughtItemCatalogueStatus.ACTIVE, None)

    if expected.refusal is None:
        assert rules.assert_merge_target(target, source) is expected.reactivates
    else:
        with pytest.raises(error):
            rules.assert_merge_target(target, source)
