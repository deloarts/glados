"""
Use cases for the default display schedule, which every screen in the
Default mode follows: reading it is open to every signed-in user, setting
it needs write:infoscreens. Saving it signals every display showing a
screen, so the ones that follow it switch at once.
"""

from src.modules.operations.application.dto.infoscreen_dto import DisplayScheduleDefaultResult
from src.modules.operations.application.dto.infoscreen_dto import SetDisplayScheduleDefaultCommand
from src.modules.operations.application.mappers.infoscreen_mapper import display_default_to_result
from src.modules.operations.application.mappers.infoscreen_mapper import schedule_from_dto
from src.modules.operations.domain.services import infoscreen_rules
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleDefault
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class GetDisplayScheduleDefault:
    def __init__(self, infoscreen_repo: IInfoscreenRepository) -> None:
        self._screens = infoscreen_repo

    async def execute(self) -> DisplayScheduleDefaultResult:
        return display_default_to_result(await self._screens.get_display_default())


class SetDisplayScheduleDefault:
    def __init__(self, infoscreen_repo: IInfoscreenRepository, *, uow: IUnitOfWork) -> None:
        self._screens = infoscreen_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: SetDisplayScheduleDefaultCommand
    ) -> DisplayScheduleDefaultResult:
        infoscreen_rules.assert_can_write(actor)
        default = DisplayScheduleDefault(
            schedule=schedule_from_dto(cmd.display_schedule),
            off_on_holidays=cmd.off_on_holidays,
        )
        saved = await self._screens.save_display_default(default)
        await self._uow.commit()
        log.info(f"{actor.full_name} set the default display schedule.")
        return display_default_to_result(saved)
