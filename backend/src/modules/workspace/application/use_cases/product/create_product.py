"""Use case for creating a new product and publishing the ProductCreated event."""

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.number_pattern import matches
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_dto import CreateProductCommand
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.application.mappers.product_mapper import ProductMapper
from src.modules.workspace.application.services import plc_environments
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.errors import ProductAlreadyExistsError
from src.modules.workspace.domain.errors import ProductNumberPatternError
from src.modules.workspace.domain.events.product_events import ProductCreated
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.shared_kernel.domain.services.clock import now_utc


class CreateProduct:
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

    async def execute(self, actor: User, cmd: CreateProductCommand) -> ProductResult:
        ProductRules.assert_can_create(actor)

        pattern = (await self._settings.get_general()).product_number_pattern
        if not matches(cmd.product_number, pattern):
            raise ProductNumberPatternError(
                f"Product number {cmd.product_number!r} does not match the "
                f"required pattern ({pattern})."
            )

        if await self._products.get_by_product_number(cmd.product_number):
            raise ProductAlreadyExistsError(
                f"A product with number {cmd.product_number!r} already exists."
            )

        if cmd.customer_id is not None and (
            not self._customers or not await self._customers.get_by_id(cmd.customer_id)
        ):
            raise CustomerNotFoundError(f"Customer #{cmd.customer_id} does not exist.")

        await plc_environments.assert_usable(self._environments, cmd.plc_environment_id, None)

        effective_user_id = ProductRules.resolve_designated_user(actor, cmd.designated_user_id)
        if not await self._users.get_by_id(effective_user_id):
            raise UserNotFoundError(f"Designated user #{effective_user_id} does not exist.")

        product = Product(
            id=0,
            product_number=cmd.product_number,
            customer_id=cmd.customer_id,
            description=cmd.description,
            designation=cmd.designation,
            machine_type=cmd.machine_type,
            installation_site=cmd.installation_site,
            installation_location=cmd.installation_location,
            planned_placing_on_market=cmd.planned_placing_on_market,
            legal_basis=cmd.legal_basis,
            plc_environment_id=cmd.plc_environment_id,
            contains_pneumatics=cmd.contains_pneumatics,
            contains_hydraulics=cmd.contains_hydraulics,
            contains_electrics=cmd.contains_electrics,
            contains_robotics=cmd.contains_robotics,
            is_active=cmd.is_active,
            designated_user_id=effective_user_id,
            created=now_utc(),
            archived=False,
            creator_id=actor.id,
        )
        saved = await self._products.save(product)

        await self._bus.publish(
            ProductCreated(
                product_id=saved.id,
                product_number=saved.product_number,
                actor_id=actor.id,
                designated_user_id=saved.designated_user_id,
            )
        )
        await self._uow.commit()

        log.info(f"Created product {saved.product_number!r} (ID={saved.id}).")

        return ProductMapper.to_result(saved)
