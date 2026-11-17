"""
Creates a new made item, validating its part number, processes, and material
source, then registers the part number and publishes MadeItemCreated.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.application.services.made_item_creation import assert_customer_data_valid
from src.modules.catalogue.application.services.made_item_creation import (
    assert_material_source_valid,
)
from src.modules.catalogue.application.services.made_item_creation import build_and_save_processes
from src.modules.catalogue.application.services.made_item_creation import validate_processes
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import WebCreationDisabledError
from src.modules.catalogue.domain.events.made_item_events import MadeItemCreated
from src.modules.catalogue.domain.policies.catalogue_item_status import assert_new_item_status
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.pdm_ownership import assert_part_number_not_pdm_reserved
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.part_number_registry import (
    IPartNumberRegistry,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateMadeItem:
    """Creates a made item. prepare() runs the checks and returns a
    non-committing closure, so PDM ingest can fold it into its own
    transaction."""

    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        article_group_repo: IArticleGroupRepository,
        bought_item_repo: IBoughtItemRepository,
        source_item_repo: ISourceItemRepository,
        fabrication_method_repo: IFabricationMethodRepository,
        inspection_method_repo: IInspectionMethodRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        *,
        cad_source: ICadSource,
        customer_repo: ICustomerRepository,
        part_number_registry: IPartNumberRegistry,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._items = made_item_repo
        self._article_groups = article_group_repo
        self._bought_items = bought_item_repo
        self._source_items = source_item_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._admin_settings = admin_settings_repo
        self._cad = cad_source
        self._customers = customer_repo
        self._registry = part_number_registry
        self._bus = event_bus
        self._uow = uow

    async def prepare(
        self, actor: User, cmd: CreateMadeItemCommand
    ) -> Callable[[], Awaitable[MadeItem]]:
        """Runs every pre-check and returns the non-committing write."""
        MadeItemCatalogueRules.assert_can_create(actor)
        assert_new_item_status(family="made item", status=MadeItemCatalogueStatus(cmd.status))
        await assert_material_source_valid(
            cmd.bought_item_id,
            cmd.source_item_id,
            cmd.article_group_ids,
            self._article_groups,
            self._bought_items,
            self._source_items,
        )
        await assert_customer_data_valid(
            actor,
            cmd.customer_id,
            cmd.customer_part_number,
            cmd.customer_revision,
            self._customers,
        )

        inspection_methods_by_id = await validate_processes(
            cmd.processes, self._fabrication_methods, self._inspection_methods
        )

        made_item_settings = await self._admin_settings.get_made_items()
        pdm_enabled = (await self._cad.policy()).connected

        # Web creation while PDM is enabled is an admin choice. Ingest, as the
        # system user, is the PDM path itself and is never blocked by it.
        if pdm_enabled and not made_item_settings.web_creation_allowed and not actor.is_systemuser:
            raise WebCreationDisabledError(
                "Web creation of made items is disabled while the PDM integration is enabled."
            )

        if (
            not made_item_settings.part_number_auto
            and cmd.part_number is not None
            and not actor.is_systemuser
        ):
            # Only a typed number can hit the PDM pattern; ingest, as the
            # system user, is exempt.
            assert_part_number_not_pdm_reserved(
                cmd.part_number, made_item_settings.pdm_part_number_pattern, enabled=pdm_enabled
            )

        now = now_utc()

        async def write() -> MadeItem:
            # Derived inside the retried write, so concurrent creates end up
            # with distinct numbers. Ingest, as the system user, brings PDM's
            # own number, which auto-numbering must never replace.
            if made_item_settings.part_number_auto and not (
                actor.is_systemuser and cmd.part_number is not None
            ):
                part_number: str | None = await self._registry.next_part_number(
                    made_item_settings.item_number_format
                )
            else:
                part_number = cmd.part_number

            if part_number is not None:
                await self._registry.claim(part_number, "made")

            # Guards against a registry and table mismatch.
            if (
                part_number is not None
                and await self._items.get_by_part_number_and_revision(part_number, cmd.revision)
                is not None
            ):
                raise MadeItemPartNumberDuplicateError(
                    f"Part number {part_number!r} is already in use."
                )

            item = MadeItem(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog([], actor.full_name, "Catalogue item created."),
                archived=False,
                revision=cmd.revision,
                revision_date=cmd.revision_date,
                revision_note=cmd.revision_note,
                article_name=cmd.article_name,
                status=MadeItemCatalogueStatus(cmd.status),
                data_source=DataSource(cmd.data_source),
                part_number=part_number,
                material=cmd.material,
                mass=cmd.mass,
                base_size=cmd.base_size,
                note=cmd.note,
                weblink=cmd.weblink,
                files=[],
                creator_id=actor.id,
                approver_id=None,
                bought_item_id=cmd.bought_item_id,
                source_item_id=cmd.source_item_id,
                article_group_ids=cmd.article_group_ids,
                successor_item_id=None,
                changed_by_id=None,
                customer_id=cmd.customer_id,
                customer_part_number=cmd.customer_part_number,
                customer_revision=cmd.customer_revision,
                creator=actor,
            )

            saved = await self._items.save(item)

            await build_and_save_processes(
                self._items, saved.id, cmd.processes, inspection_methods_by_id, actor.id, now
            )

            # A rolled-back attempt discards this staged event too.
            await self._bus.publish(
                MadeItemCreated(
                    item_id=saved.id,
                    article_name=saved.article_name,
                    creator_id=saved.creator_id,
                )
            )
            return saved

        return write

    async def execute(self, actor: User, cmd: CreateMadeItemCommand) -> MadeItemResult:
        write = await self.prepare(actor, cmd)

        # Safe to retry, because write() builds everything from `cmd`.
        saved = await commit_with_number_retry(self._uow, write)

        if cmd.processes:
            saved = await self._items.get_by_id(saved.id) or saved

        log.info(f"Created made-item catalogue item {saved.article_name!r}, ID={saved.id}.")

        return MadeItemMapper.to_result(saved)
