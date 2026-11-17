"""
Creates a new Project after checking the actor's permission, the admin-configured project
number pattern and headless-project policy, project number uniqueness, and the existence of any
referenced customer, product, and designated user. Publishes ProjectCreated on success.
"""

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
from src.modules.workspace.application.dto.project_dto import CreateProjectCommand
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.application.mappers.project_mapper import ProjectMapper
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.errors import ProjectAlreadyExistsError
from src.modules.workspace.domain.errors import ProjectNumberPatternError
from src.modules.workspace.domain.errors import ProjectProductRequiredError
from src.modules.workspace.domain.events.project_events import ProjectCreated
from src.modules.workspace.domain.services.project_rules import ProjectRules
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateProject:
    def __init__(
        self,
        project_repo: IProjectRepository,
        user_repo: IUserRepository,
        product_repo: IProductRepository | None = None,
        customer_repo: ICustomerQueries | None = None,
        *,
        event_bus: IEventBus,
        settings_repo: ICatalogueSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._projects = project_repo
        self._users = user_repo
        self._products = product_repo
        self._customers = customer_repo
        self._bus = event_bus
        self._settings = settings_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateProjectCommand) -> ProjectResult:
        # 1. Permission check
        ProjectRules.assert_can_create(actor)

        # 1b. Admin-configured policy
        general = await self._settings.get_general()
        if not matches(cmd.project_number, general.project_number_pattern):
            raise ProjectNumberPatternError(
                f"Project number {cmd.project_number!r} does not match the "
                f"required pattern ({general.project_number_pattern})."
            )
        if not general.allow_headless_projects and cmd.product_id is None:
            raise ProjectProductRequiredError("A project must reference a product.")

        # 2. Uniqueness check
        if await self._projects.get_by_project_number(cmd.project_number):
            raise ProjectAlreadyExistsError(
                f"A project with number {cmd.project_number!r} already exists."
            )

        # 3. Customer must exist if provided
        if cmd.customer_id is not None and (
            not self._customers or not await self._customers.get_by_id(cmd.customer_id)
        ):
            raise CustomerNotFoundError(f"Customer #{cmd.customer_id} does not exist.")

        # 4. Product must exist if provided
        if cmd.product_id is not None and (
            not self._products or not await self._products.get_by_id(cmd.product_id)
        ):
            raise ProductNotFoundError(f"Product #{cmd.product_id} does not exist.")

        # 5. Designated user must exist
        effective_user_id = ProjectRules.resolve_designated_user(actor, cmd.designated_user_id)
        if not await self._users.get_by_id(effective_user_id):
            raise UserNotFoundError(f"Designated user #{effective_user_id} does not exist.")

        # 6. Build and persist
        now = now_utc()
        project = Project(
            id=0,
            project_number=cmd.project_number,
            customer_id=cmd.customer_id,
            product_id=cmd.product_id,
            description=cmd.description,
            status=cmd.status,
            designated_user_id=effective_user_id,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Project created."),
            deleted=False,
            creator_id=actor.id,
            production_time_budget=cmd.production_time_budget,
            required_delivery_date_made=cmd.required_delivery_date_made,
            required_delivery_date_bought=cmd.required_delivery_date_bought,
        )
        saved = await self._projects.save(project)

        await self._bus.publish(
            ProjectCreated(
                project_id=saved.id,
                project_number=saved.project_number,
                actor_id=actor.id,
                designated_user_id=saved.designated_user_id,
            )
        )
        await self._uow.commit()

        log.info(f"Created project {saved.project_number!r} (ID={saved.id}).")

        return ProjectMapper.to_result(saved)
