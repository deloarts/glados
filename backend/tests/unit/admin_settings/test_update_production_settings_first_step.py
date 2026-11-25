"""
UpdateProductionSettings keeps external_first_step_needs_no_material: on by
default, stored when it is sent, and left as it is when it is not. Turning
it off restores the material need of the lots it took it from, with the
approval setting the same save stores; turning it on restores nothing.
"""

from datetime import datetime

from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    UpdateProductionSettingsCommand,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_production_settings import (
    UpdateProductionSettings,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.admin_settings.fakes import FakeInspectionMethodRepository
from tests.unit.fakes import FakeUnitOfWork


class _NoLots:
    async def reset_source_approval_for_setting_change(self, enabled: bool) -> int:
        return 0


class _RecordingRestore:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def restore(self, actor: User, now: datetime, *, approval_required: bool) -> int:
        self.calls.append(approval_required)
        return 0


def _use_case(
    repo: FakeAdminSettingsRepository, restore: _RecordingRestore | None = None
) -> UpdateProductionSettings:
    return UpdateProductionSettings(
        repo,
        FakeInspectionMethodRepository(),
        _NoLots(),  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
        material_restore=restore or _RecordingRestore(),  # type: ignore[arg-type]
    )


ACTOR = make_user(permissions=[Permission.WRITE_SETTINGS])


async def test_on_by_default() -> None:
    assert FakeAdminSettingsRepository().production.external_first_step_needs_no_material is True


async def test_turning_it_off_is_stored_and_restores_the_lots() -> None:
    repo = FakeAdminSettingsRepository()
    restore = _RecordingRestore()

    result = await _use_case(repo, restore).execute(
        ACTOR,
        UpdateProductionSettingsCommand(
            external_first_step_needs_no_material=False, require_source_item_approval=True
        ),
    )

    assert result.external_first_step_needs_no_material is False
    assert (await repo.get_production()).external_first_step_needs_no_material is False
    assert restore.calls == [True]


async def test_turning_it_on_restores_nothing() -> None:
    repo = FakeAdminSettingsRepository()
    repo.production.external_first_step_needs_no_material = False
    restore = _RecordingRestore()

    await _use_case(repo, restore).execute(
        ACTOR, UpdateProductionSettingsCommand(external_first_step_needs_no_material=True)
    )

    assert restore.calls == []


async def test_an_update_without_it_keeps_it() -> None:
    repo = FakeAdminSettingsRepository()
    repo.production.external_first_step_needs_no_material = False
    restore = _RecordingRestore()

    result = await _use_case(repo, restore).execute(
        ACTOR, UpdateProductionSettingsCommand(response_time_days=3)
    )

    assert result.external_first_step_needs_no_material is False
    assert restore.calls == []
