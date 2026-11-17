"""
Unit tests for TestUpdateOrderSettings and TestUpdateMadeItemSettings.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

import re

import pytest

from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    RevisionFieldPolicyEntry,
)
from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    UpdateMadeItemSettingsCommand,
)
from src.modules.catalogue.application.dto.admin_settings_dto.orders import (
    UpdateOrderSettingsCommand,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_made_item_settings import (
    UpdateMadeItemSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_order_settings import (
    UpdateOrderSettings,
)
from src.modules.catalogue.domain.policies.item_field_ownership import REVISION_POLICY_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.numbering_format import render_example
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services.clock import today_utc
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.fakes import FakeUnitOfWork


class TestUpdateOrderSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateOrderSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateOrderSettingsCommand(order_number_format="PO-{year}-{seq:03d}"),
        )
        assert result.order_number_format == "PO-{year}-{seq:03d}"

    async def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateOrderSettingsCommand(order_number_format="NOSEQ")
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateOrderSettingsCommand())

    async def test_partial_update_preserves_web_creation_allowed(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateOrderSettingsCommand(web_creation_allowed=False)
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateOrderSettingsCommand(order_number_format="PO-{year}-{seq:03d}"),
        )
        assert result.web_creation_allowed is False

    async def test_updates_web_creation_allowed(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateOrderSettingsCommand(web_creation_allowed=False),
        )
        assert result.web_creation_allowed is False

    async def test_updates_pdm_part_number_pattern(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateOrderSettingsCommand(pdm_part_number_pattern=r"^EXT-\d+$"),
        )
        assert result.pdm_part_number_pattern == r"^EXT-\d+$"

    async def test_invalid_pdm_pattern_rejected(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateOrderSettingsCommand(pdm_part_number_pattern="[")
            )

    async def test_pdm_pattern_overlapping_part_number_format_rejected(self):
        example = render_example(self.repo.orders.part_number_format, today=today_utc())
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateOrderSettingsCommand(pdm_part_number_pattern=re.escape(example)),
            )

    async def test_pdm_pattern_overlapping_order_number_format_rejected(self):
        example = render_example(self.repo.orders.order_number_format, today=today_utc())
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateOrderSettingsCommand(pdm_part_number_pattern=re.escape(example)),
            )


class TestUpdateMadeItemSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateMadeItemSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(item_number_format="MI-{year}-{seq:03d}"),
        )
        assert result.item_number_format == "MI-{year}-{seq:03d}"

    async def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateMadeItemSettingsCommand(item_number_format="NOSEQ")
            )

    async def test_document_number_formats_are_saved_and_validated(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(
                calculation_number_format="BER-{year}-{seq:03d}",
                checklist_number_format="PL-{seq:05d}",
            ),
        )
        assert (result.calculation_number_format, result.checklist_number_format) == (
            "BER-{year}-{seq:03d}",
            "PL-{seq:05d}",
        )
        assert result.checklist_example == "PL-00001"
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(calculation_number_format="NOSEQ"),
            )

    async def test_updates_and_validates_the_meeting_number_format(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(meeting_number_format="BSP-{yy}-{seq:03d}"),
        )
        assert result.meeting_number_format == "BSP-{yy}-{seq:03d}"
        assert result.meeting_example.startswith("BSP-")
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(meeting_number_format="NOSEQ"),
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateMadeItemSettingsCommand())

    async def test_partial_update_preserves_web_creation_allowed(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateMadeItemSettingsCommand(web_creation_allowed=False)
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(item_number_format="MI-{year}-{seq:03d}"),
        )
        assert result.web_creation_allowed is False

    async def test_updates_web_creation_allowed(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(web_creation_allowed=False),
        )
        assert result.web_creation_allowed is False

    # ── Revisions ────────────────────────────────────────────────────

    async def test_partial_update_preserves_revision_start(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateMadeItemSettingsCommand(revision_start="A")
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(item_number_format="MI-{year}-{seq:03d}"),
        )
        assert result.revision_start == "A"

    async def test_updates_revision_start(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateMadeItemSettingsCommand(revision_start="1")
        )
        assert result.revision_start == "1"

    async def test_invalid_revision_start_rejected(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateMadeItemSettingsCommand(revision_start="Z")
            )

    async def test_revision_separator_is_free_text(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateMadeItemSettingsCommand(revision_separator=" rev ")
        )
        assert result.revision_separator == " rev "

    async def test_updates_revision_skip_ambiguous_letters(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(revision_skip_ambiguous_letters=True),
        )
        assert result.revision_skip_ambiguous_letters is True

    async def test_updates_revision_only_newest_editable(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(revision_only_newest_editable=False),
        )
        assert result.revision_only_newest_editable is False

    async def test_predecessor_status_web_accepts_ask(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(revision_predecessor_status_web="ask"),
        )
        assert result.revision_predecessor_status_web == "ask"

    async def test_predecessor_status_web_accepts_a_status(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(revision_predecessor_status_web="inactive"),
        )
        assert result.revision_predecessor_status_web == "inactive"

    async def test_invalid_predecessor_status_web_rejected(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(revision_predecessor_status_web="bogus"),
            )

    async def test_predecessor_status_pdm_rejects_ask(self):
        """Unlike the web setting, "ask" has no meaning for ingest: there is
        no user to ask, so it is not in the allowed set for this field."""
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(revision_predecessor_status_pdm="ask"),
            )

    async def test_updates_predecessor_status_pdm(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(revision_predecessor_status_pdm="active"),
        )
        assert result.revision_predecessor_status_pdm == "active"

    async def test_invalid_predecessor_status_pdm_rejected(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(revision_predecessor_status_pdm="bogus"),
            )

    async def test_updates_revision_field_policy(self):
        toggled = [
            RevisionFieldPolicyEntry(
                field=p.field,
                web_requires_revision=not p.web_requires_revision,
                pdm_update_in_place=p.pdm_update_in_place,
            )
            for p in default_policy()
        ]
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(revision_field_policy=toggled),
        )
        by_field = {p.field: p for p in result.revision_field_policy}
        for original in default_policy():
            assert by_field[original.field].web_requires_revision != original.web_requires_revision

    async def test_partial_update_preserves_revision_field_policy(self):
        toggled = [
            RevisionFieldPolicyEntry(
                field=p.field, web_requires_revision=True, pdm_update_in_place=True
            )
            for p in default_policy()
        ]
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateMadeItemSettingsCommand(revision_field_policy=toggled)
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(item_number_format="MI-{year}-{seq:03d}"),
        )
        assert all(p.web_requires_revision for p in result.revision_field_policy)
        assert all(p.pdm_update_in_place for p in result.revision_field_policy)

    @staticmethod
    def _policy_entry(field: str) -> RevisionFieldPolicyEntry:
        return RevisionFieldPolicyEntry(
            field=field, web_requires_revision=False, pdm_update_in_place=False
        )

    async def test_revision_field_policy_missing_field_rejected(self):
        incomplete = [self._policy_entry(f) for f in REVISION_POLICY_FIELDS[:-1]]
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(revision_field_policy=incomplete),
            )

    async def test_revision_field_policy_unknown_field_rejected(self):
        bogus = [self._policy_entry(f) for f in (*REVISION_POLICY_FIELDS, "not_a_field")]
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateMadeItemSettingsCommand(revision_field_policy=bogus)
            )

    async def test_revision_field_policy_duplicate_field_rejected(self):
        duplicated = [self._policy_entry(f) for f in REVISION_POLICY_FIELDS[:-1]] + [
            self._policy_entry(REVISION_POLICY_FIELDS[0]),
            self._policy_entry(REVISION_POLICY_FIELDS[0]),
        ]
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(revision_field_policy=duplicated),
            )

    async def test_updates_pdm_part_number_pattern(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(pdm_part_number_pattern=r"^EXT-\d+$"),
        )
        assert result.pdm_part_number_pattern == r"^EXT-\d+$"

    async def test_invalid_pdm_pattern_rejected(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateMadeItemSettingsCommand(pdm_part_number_pattern="[")
            )

    async def test_pdm_pattern_overlapping_item_number_format_rejected(self):
        example = render_example(self.repo.made_items.item_number_format, today=today_utc())
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateMadeItemSettingsCommand(pdm_part_number_pattern=re.escape(example)),
            )

    async def test_pdm_pattern_overlapping_lot_number_format_is_allowed(self):
        """Lot numbers are not part numbers: a pattern matching
        the lot-number format's example is not rejected."""
        example = render_example(self.repo.made_items.lot_number_format, today=today_utc())
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMadeItemSettingsCommand(pdm_part_number_pattern=re.escape(example)),
        )
        assert result.pdm_part_number_pattern == re.escape(example)
