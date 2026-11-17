"""
Lists, creates, edits, archives and restores PLC environments, and hands
out the settings a new one starts from. They are device resources, so
editing and archiving need write:product_device_resources. Exactly one live environment is the
default: marking one takes the mark from the others, and the default can
be neither archived nor taken off without another taking its place.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.plc_environment_dto import CharConversionDto
from src.modules.workspace.application.dto.plc_environment_dto import ExportColumnDto
from src.modules.workspace.application.dto.plc_environment_dto import PlcEnvironmentResult
from src.modules.workspace.application.dto.plc_environment_dto import PlcEnvironmentSettings
from src.modules.workspace.application.dto.plc_environment_dto import SavePlcEnvironmentCommand
from src.modules.workspace.application.mappers.plc_environment_mapper import to_result
from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.errors import PlcEnvironmentDefaultError
from src.modules.workspace.domain.errors import PlcEnvironmentNameTakenError
from src.modules.workspace.domain.errors import PlcEnvironmentNotFoundError
from src.modules.workspace.domain.services.plc_environment_rules import apply_settings
from src.modules.workspace.domain.services.product_device_resource_rules import (
    ProductDeviceResourceRules,
)
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_CONVERSIONS
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_EXPORT_COLUMNS
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_EXPORT_SHEET
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_MAX_TAG_LENGTH
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_NAME
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_PREFIXES
from src.modules.workspace.domain.value_objects.plc_environment_settings import TIA_TAG_TABLE
from src.modules.workspace.domain.value_objects.plc_environment_settings import CharConversion
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumn
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


def tia_template() -> PlcEnvironmentSettings:
    """The settings of Siemens TIA Portal, which a new environment starts from."""
    return PlcEnvironmentSettings(
        name=TIA_NAME,
        prefixes=dict(TIA_PREFIXES),
        max_tag_length=TIA_MAX_TAG_LENGTH,
        conversions=[CharConversionDto(source=c.source, target=c.target) for c in TIA_CONVERSIONS],
        tag_table=TIA_TAG_TABLE,
        safety_tag_table=None,
        export_sheet=TIA_EXPORT_SHEET,
        export_columns=[
            ExportColumnDto(header=c.header, source=c.source, value=c.value)
            for c in TIA_EXPORT_COLUMNS
        ],
    )


def _apply(environment: PlcEnvironment, cmd: SavePlcEnvironmentCommand) -> None:
    apply_settings(
        environment,
        name=cmd.name,
        prefixes=cmd.prefixes,
        max_tag_length=cmd.max_tag_length,
        conversions=[CharConversion(c.source, c.target) for c in cmd.conversions],
        tag_table=cmd.tag_table,
        safety_tag_table=cmd.safety_tag_table,
        export_sheet=cmd.export_sheet,
        export_columns=[ExportColumn(c.header, c.source, c.value) for c in cmd.export_columns],
    )


class GetPlcEnvironments:
    def __init__(self, environment_repo: IPlcEnvironmentRepository) -> None:
        self._environments = environment_repo

    async def execute(self, include_archived: bool) -> list[PlcEnvironmentResult]:
        return [to_result(e) for e in await self._environments.get_many(include_archived)]


class GetPlcEnvironmentTemplate:
    async def execute(self) -> PlcEnvironmentSettings:
        return tia_template()


class _Writer:
    def __init__(self, environment_repo: IPlcEnvironmentRepository, *, uow: IUnitOfWork) -> None:
        self._environments = environment_repo
        self._uow = uow

    async def _assert_name_free(self, environment: PlcEnvironment) -> None:
        other = await self._environments.get_live_by_name(environment.name)
        if other is not None and other.id != environment.id:
            raise PlcEnvironmentNameTakenError(
                f"A PLC environment named {environment.name!r} already exists."
            )

    async def _store(self, environment: PlcEnvironment) -> PlcEnvironment:
        await self._assert_name_free(environment)
        saved = await self._environments.save(environment)
        if saved.is_default:
            await self._environments.clear_default_except(saved.id)
        await self._uow.commit()
        return saved


class CreatePlcEnvironment(_Writer):
    async def execute(self, actor: User, cmd: SavePlcEnvironmentCommand) -> PlcEnvironmentResult:
        ProductDeviceResourceRules.assert_can_write(actor)
        now = now_utc()
        # The first environment is the default, so products always have one.
        first = await self._environments.get_default() is None
        environment = PlcEnvironment(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "PLC environment created."),
            name="",
            is_default=cmd.is_default or first,
            prefixes={},
            max_tag_length=0,
            conversions=[],
            tag_table="",
            safety_tag_table=None,
            export_sheet="",
            export_columns=[],
            creator_id=actor.id,
        )
        _apply(environment, cmd)
        saved = await self._store(environment)
        log.info(f"Created PLC environment ID={saved.id}.")
        return to_result(saved)


class UpdatePlcEnvironment(_Writer):
    async def execute(
        self, actor: User, environment_id: int, cmd: SavePlcEnvironmentCommand
    ) -> PlcEnvironmentResult:
        ProductDeviceResourceRules.assert_can_write(actor)
        environment = found_or_raise(
            await self._environments.get_by_id(environment_id),
            PlcEnvironmentNotFoundError,
            f"PLC environment #{environment_id} not found.",
        )
        if environment.is_default and not cmd.is_default:
            raise PlcEnvironmentDefaultError(
                f"PLC environment #{environment_id} is the default; make another one the "
                "default instead."
            )
        if cmd.is_default and environment.archived:
            raise PlcEnvironmentDefaultError(
                f"PLC environment #{environment_id} is archived and cannot be the default."
            )
        _apply(environment, cmd)
        environment.is_default = cmd.is_default
        environment.changed = now_utc()
        environment.changes = append_changelog(
            environment.changes, actor.full_name, "PLC environment updated."
        )
        saved = await self._store(environment)
        log.info(f"Updated PLC environment ID={saved.id}.")
        return to_result(saved)


class SetPlcEnvironmentArchived:
    def __init__(self, environment_repo: IPlcEnvironmentRepository, *, uow: IUnitOfWork) -> None:
        self._environments = environment_repo
        self._uow = uow

    async def execute(
        self, actor: User, environment_id: int, archived: bool
    ) -> PlcEnvironmentResult:
        ProductDeviceResourceRules.assert_can_archive(actor)
        environment = found_or_raise(
            await self._environments.get_by_id(environment_id),
            PlcEnvironmentNotFoundError,
            f"PLC environment #{environment_id} not found.",
        )
        if archived and environment.is_default:
            raise PlcEnvironmentDefaultError(
                f"PLC environment #{environment_id} is the default and cannot be archived."
            )
        if not archived:
            other = await self._environments.get_live_by_name(environment.name)
            if other is not None and other.id != environment.id:
                raise PlcEnvironmentNameTakenError(
                    f"A live PLC environment named {environment.name!r} already exists."
                )
        environment.archived = archived
        environment.changed = now_utc()
        environment.changes = append_changelog(
            environment.changes,
            actor.full_name,
            "PLC environment archived." if archived else "PLC environment restored.",
        )
        saved = await self._environments.save(environment)
        await self._uow.commit()
        log.info(f"{'Archived' if archived else 'Restored'} PLC environment ID={saved.id}.")
        return to_result(saved)
