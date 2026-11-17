"""
Creates and updates saved calculations. The inputs and results are stored
as the tool sent them; the backend never interprets them. An update
replaces both and may move a draft to another owner. A new calculation
starts at the revision the admin settings name as the first one, the same
start value made items use, and gets the next document number of the
calculation numbering format. An update is saved only by the holder of the
edit lock, who is then remembered as one of its editors. A referenced
device must belong to the calculation's product or its project's product.
The device of a draft can also be set or cleared on its own, from the
device's side, without editing the calculation.
"""

from dataclasses import replace

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CreateCalculationCommand
from src.modules.quality.application.dto.calculation_dto import UpdateCalculationCommand
from src.modules.quality.application.mappers.calculation_mapper import CalculationMapper
from src.modules.quality.application.services import controlled_documents
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.services import document_control
from src.modules.quality.domain.services.calculation_rules import CalculationRules
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)
from src.modules.workspace.domain.policies.product_device_rules import check_document_device
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc


class _CalculationWriter:
    def __init__(
        self,
        calculation_repo: ICalculationRepository,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        device_repo: IProductDeviceQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._calculations = calculation_repo
        self._projects = project_repo
        self._products = product_repo
        self._devices = device_repo
        self._uow = uow

    @staticmethod
    def _snapshot(calculation: Calculation) -> dict[str, object]:
        return {
            "title": calculation.title,
            "note": calculation.note,
            "input_version": calculation.input_version,
            "engine_version": calculation.engine_version,
            "project_id": calculation.project_id,
            "product_id": calculation.product_id,
            "product_device_id": calculation.product_device_id,
        }

    async def _assert_device_fits(
        self,
        device_id: int | None,
        project_id: int | None,
        product_id: int | None,
        current_id: int | None,
    ) -> None:
        """A referenced device must belong to the calculation's product, or
        to the product of its project."""
        if device_id is None:
            return
        owner_product_id = product_id
        if owner_product_id is None and project_id is not None:
            project = await self._projects.get_by_id(project_id)
            owner_product_id = project.product_id if project else None
        check_document_device(
            await self._devices.get_by_id(device_id), owner_product_id, current_id
        )

    async def _assert_owner_exists(self, project_id: int | None, product_id: int | None) -> None:
        await controlled_documents.assert_owner_exists(
            self._projects,
            self._products,
            project_id,
            product_id,
            valid_owner=CalculationRules.assert_valid_owner,
            plural="calculations",
        )


class CreateCalculation(_CalculationWriter):
    def __init__(
        self,
        calculation_repo: ICalculationRepository,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        admin_settings_repo: IFulfillmentSettingsRepository,
        device_repo: IProductDeviceQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(calculation_repo, project_repo, product_repo, device_repo, uow=uow)
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User, cmd: CreateCalculationCommand) -> CalculationResult:
        CalculationRules.assert_can_create(actor)
        await self._assert_owner_exists(cmd.project_id, cmd.product_id)
        await self._assert_device_fits(
            cmd.product_device_id, cmd.project_id, cmd.product_id, current_id=None
        )
        settings = await self._admin_settings.get_made_items()

        now = now_utc()
        calculation = Calculation(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Calculation saved."),
            tool=cmd.tool,
            title=cmd.title,
            note=cmd.note,
            inputs=cmd.inputs,
            results=cmd.results,
            input_version=cmd.input_version,
            engine_version=cmd.engine_version,
            project_id=cmd.project_id,
            product_id=cmd.product_id,
            product_device_id=cmd.product_device_id,
            creator_id=actor.id,
            revision=settings.revision_start,
        )

        async def write() -> Calculation:
            number = await self._calculations.next_document_number(
                settings.calculation_number_format
            )
            return await self._calculations.save(replace(calculation, document_number=number))

        saved = await commit_with_number_retry(self._uow, write)
        log.info("Calculation #%s (%s) saved by user #%s.", saved.id, saved.tool, actor.id)
        return CalculationMapper.to_result(saved)


class UpdateCalculation(_CalculationWriter):
    async def execute(
        self, actor: User, calculation_id: int, cmd: UpdateCalculationCommand
    ) -> CalculationResult:
        CalculationRules.assert_can_write(actor, "update")
        calculation = found_or_raise(
            await self._calculations.get_for_update(calculation_id),
            CalculationNotFoundError,
            f"Calculation #{calculation_id} not found.",
        )
        CalculationRules.assert_can_update(actor, calculation)
        now = now_utc()
        document_control.assert_holds_lock(
            calculation, actor, now, f"Calculation #{calculation.id}"
        )
        document_control.renew_lock(calculation, actor, now)
        document_control.record_editor(calculation, actor)
        if (cmd.project_id, cmd.product_id) != (calculation.project_id, calculation.product_id):
            await self._assert_owner_exists(cmd.project_id, cmd.product_id)
        await self._assert_device_fits(
            cmd.product_device_id,
            cmd.project_id,
            cmd.product_id,
            current_id=calculation.product_device_id,
        )

        old = self._snapshot(calculation)
        calculation.title = cmd.title
        calculation.note = cmd.note
        calculation.input_version = cmd.input_version
        calculation.engine_version = cmd.engine_version
        calculation.project_id = cmd.project_id
        calculation.product_id = cmd.product_id
        calculation.product_device_id = cmd.product_device_id
        new = self._snapshot(calculation)

        lines = [diff_changes(old, new, heading="Calculation updated:")]
        if cmd.inputs != calculation.inputs:
            lines.append("Inputs changed.")
        if cmd.results != calculation.results:
            lines.append("Results changed.")
        calculation.inputs = cmd.inputs
        calculation.results = cmd.results
        calculation.changed = now
        calculation.changed_by_id = actor.id
        calculation.changed_by_full_name = actor.full_name
        calculation.changes = append_changelog(
            calculation.changes, actor.full_name, "\n".join(line for line in lines if line)
        )

        saved = await self._calculations.save(calculation)
        await self._uow.commit()
        log.info("Calculation #%s updated by user #%s.", saved.id, actor.id)
        return CalculationMapper.to_result(saved)


class SetCalculationDevice(_CalculationWriter):
    """Links a draft to a device of its product, or unlinks it. Its creator
    or a manager may, as for any change of a draft, but not while someone
    else is editing it. A released revision keeps the device it was released
    with, so changing that link needs a new revision."""

    async def execute(
        self, actor: User, calculation_id: int, device_id: int | None
    ) -> CalculationResult:
        CalculationRules.assert_can_write(actor, "update")
        calculation = found_or_raise(
            await self._calculations.get_for_update(calculation_id),
            CalculationNotFoundError,
            f"Calculation #{calculation_id} not found.",
        )
        CalculationRules.assert_can_update(actor, calculation)
        now = now_utc()
        document_control.assert_not_locked_by_other(
            calculation, actor, now, f"Calculation #{calculation.id}"
        )
        if device_id == calculation.product_device_id:
            return CalculationMapper.to_result(calculation)
        await self._assert_device_fits(
            device_id,
            calculation.project_id,
            calculation.product_id,
            current_id=calculation.product_device_id,
        )

        old = self._snapshot(calculation)
        calculation.product_device_id = device_id
        calculation.changed = now
        calculation.changed_by_id = actor.id
        calculation.changed_by_full_name = actor.full_name
        calculation.changes = append_changelog(
            calculation.changes,
            actor.full_name,
            diff_changes(old, self._snapshot(calculation), heading="Calculation updated:"),
        )
        saved = await self._calculations.save(calculation)
        await self._uow.commit()
        log.info("Calculation #%s linked to device #%s by user #%s.", saved.id, device_id, actor.id)
        return CalculationMapper.to_result(saved)
