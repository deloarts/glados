"""
Updates a product's editable fields, re-validating the product number against the
current numbering pattern and uniqueness only when it actually changes. Reassigning
the designated user goes through a separate permission check so an update that omits
the field never silently transfers ownership, and the change is published as a
ProductUpdated event.
"""

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.number_pattern import matches
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.application.dto.product_dto import UpdateProductCommand
from src.modules.workspace.application.mappers.product_mapper import ProductMapper
from src.modules.workspace.application.services import plc_environments
from src.modules.workspace.domain.errors import ProductAlreadyExistsError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.errors import ProductNumberPatternError
from src.modules.workspace.domain.events.product_events import ProductUpdated
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class UpdateProduct:
    def __init__(
        self,
        product_repo: IProductRepository,
        user_repo: IUserRepository,
        customer_repo: ICustomerQueries | None = None,
        *,
        event_bus: IEventBus,
        settings_repo: ICatalogueSettingsRepository,
        uow: IUnitOfWork,
        environment_repo: IPlcEnvironmentRepository | None = None,
    ) -> None:
        self._environments = environment_repo
        self._products = product_repo
        self._users = user_repo
        self._customers = customer_repo
        self._bus = event_bus
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, product_id: int, cmd: UpdateProductCommand
    ) -> ProductResult:
        await self._products.lock_for_update(product_id)
        product = found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        assert_edit_version(product, cmd.expected_edit_version, what=f"Product #{product.id}")

        ProductRules.assert_can_update(actor, product)

        # Only checked when the number actually changes: a product numbered
        # before an admin set or tightened the pattern stays editable, so
        # the rule does not block every other edit to such a product until
        # it is renumbered.
        if cmd.product_number != product.product_number:
            pattern = (await self._settings.get_general()).product_number_pattern
            if not matches(cmd.product_number, pattern):
                raise ProductNumberPatternError(
                    f"Product number {cmd.product_number!r} does not match the "
                    f"required pattern ({pattern})."
                )

            existing = await self._products.get_by_product_number(cmd.product_number)
            if existing and existing.id != product.id:
                raise ProductAlreadyExistsError(
                    f"A product with number {cmd.product_number!r} already exists."
                )

        if cmd.customer_id is not None and (
            not self._customers or not await self._customers.get_by_id(cmd.customer_id)
        ):
            raise CustomerNotFoundError(f"Customer #{cmd.customer_id} does not exist.")

        await plc_environments.assert_usable(
            self._environments, cmd.plc_environment_id, product.plc_environment_id
        )

        if cmd.designated_user_id is None:
            # Omitted means "leave the owner alone". Resolving it to the
            # actor the way CreateProduct does would let any update that
            # forgets the field silently transfer ownership.
            effective_user_id = product.designated_user_id
        else:
            ProductRules.assert_can_assign_designated_user(actor, cmd.designated_user_id)
            if not await self._users.get_by_id(cmd.designated_user_id):
                raise UserNotFoundError(
                    f"Designated user #{cmd.designated_user_id} does not exist."
                )
            effective_user_id = cmd.designated_user_id

        old_designated_user_id = product.designated_user_id

        product.product_number = cmd.product_number
        product.customer_id = cmd.customer_id
        product.description = cmd.description
        product.designation = cmd.designation
        product.machine_type = cmd.machine_type
        product.installation_site = cmd.installation_site
        product.installation_location = cmd.installation_location
        product.planned_placing_on_market = cmd.planned_placing_on_market
        product.legal_basis = cmd.legal_basis
        product.plc_environment_id = cmd.plc_environment_id
        product.contains_pneumatics = cmd.contains_pneumatics
        product.contains_hydraulics = cmd.contains_hydraulics
        product.contains_electrics = cmd.contains_electrics
        product.contains_robotics = cmd.contains_robotics
        product.designated_user_id = effective_user_id
        if cmd.is_active is not None:
            product.is_active = cmd.is_active

        saved = await self._products.save(product)

        await self._bus.publish(
            ProductUpdated(
                product_id=saved.id,
                product_number=saved.product_number,
                actor_id=actor.id,
                designated_user_id=saved.designated_user_id,
                old_designated_user_id=old_designated_user_id,
            )
        )
        await self._uow.commit()

        log.info(f"Updated product {saved.product_number!r} (ID={saved.id}).")

        return ProductMapper.to_result(saved)
