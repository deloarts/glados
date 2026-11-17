"""Creates a new revision by copying the newest revision of a made-item family
onto a new row with the same part number (files are never copied) and sets the
predecessor's status, linking it as successor when it becomes `replaced` and
dropping a successor it no longer may name otherwise. The web takes the
predecessor status from the admin setting and the request only while that
setting is "ask". When PDM ingest overrides a successor a person had set, a
changelog line records it. Validation is shared with CreateMadeItem.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.application.services.made_item_creation import assert_customer_data_valid
from src.modules.catalogue.application.services.made_item_creation import (
    assert_material_source_valid,
)
from src.modules.catalogue.application.services.made_item_creation import build_and_save_processes
from src.modules.catalogue.application.services.made_item_creation import validate_processes
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import MadeItemRevisionManagedByPdmError
from src.modules.catalogue.domain.events.made_item_events import MadeItemCreated
from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.catalogue_item_status import SuccessorFacts
from src.modules.catalogue.domain.policies.catalogue_item_status import (
    assert_catalogue_status_change,
)
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import newest_of
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
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
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# The web predecessor setting's value that leaves the choice to the request.
_ASK = "ask"


@dataclass
class PreparedRevision:
    """The non-committing `write` closure plus what execute() logs."""

    write: Callable[[], Awaitable[MadeItem]]
    predecessor_id: int
    next_revision: str


class CreateMadeItemRevision:
    """Creates a new revision. prepare() runs the checks and returns a
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
        self._customers = customer_repo
        self._registry = part_number_registry
        self._bus = event_bus
        self._uow = uow

    async def prepare(
        self, actor: User, item_id: int, cmd: CreateMadeItemRevisionCommand
    ) -> PreparedRevision:
        """Runs every pre-check and returns the non-committing write."""
        MadeItemCatalogueRules.assert_can_update(actor)

        source = found_or_raise(
            await self._items.get_by_id(item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )

        self._assert_source_revisable(actor, source, item_id)
        newest = await self._resolve_newest(source, item_id)

        made_item_settings = await self._admin_settings.get_made_items()
        next_rev = self._resolve_next_revision(cmd, newest, made_item_settings)
        predecessor_status = self._predecessor_status(actor, cmd, made_item_settings)

        pn = source.part_number
        if (
            pn is not None
            and await self._items.get_by_part_number_and_revision(pn, next_rev) is not None
        ):
            raise MadeItemPartNumberDuplicateError(
                f"Part number {pn!r} already has a revision {next_rev!r}."
            )

        await assert_material_source_valid(
            cmd.item.bought_item_id,
            cmd.item.source_item_id,
            cmd.item.article_group_ids,
            self._article_groups,
            self._bought_items,
            self._source_items,
        )
        await assert_customer_data_valid(
            actor,
            cmd.item.customer_id,
            cmd.item.customer_part_number,
            cmd.item.customer_revision,
            self._customers,
        )
        inspection_methods_by_id = await validate_processes(
            cmd.item.processes, self._fabrication_methods, self._inspection_methods
        )

        now = now_utc()
        data_source = cmd.data_source if cmd.data_source is not None else DataSource.WEB.value

        async def write() -> MadeItem:
            return await self._write_revision(
                actor,
                source,
                cmd,
                pn,
                next_rev,
                predecessor_status,
                data_source,
                now,
                inspection_methods_by_id,
            )

        return PreparedRevision(
            write=write,
            predecessor_id=source.id,
            next_revision=next_rev,
        )

    def _assert_source_revisable(self, actor: User, source: MadeItem, item_id: int) -> None:
        """Revisions of a CAD family come only from PDM, whatever the
        integration settings; only the system user (ingest) may create one."""
        if source.data_source == DataSource.CAD.value and not actor.is_systemuser:
            raise MadeItemRevisionManagedByPdmError(
                f"Catalogue item #{item_id}'s revisions are managed by PDM."
            )

    async def _resolve_newest(self, source: MadeItem, item_id: int) -> MadeItem:
        """The family's newest row, since incrementing an older one could
        land behind an existing sibling."""
        siblings = (
            await self._items.get_revisions(source.part_number)
            if source.part_number is not None
            else [source]
        )
        newest = newest_of(siblings)
        if newest.id != source.id:
            raise MadeItemNotNewestRevisionError(
                f"Catalogue item #{item_id} is not the newest revision of part number "
                f"{source.part_number!r}; request a new revision from the newest one instead."
            )
        return newest

    @staticmethod
    def _predecessor_status(
        actor: User, cmd: CreateMadeItemRevisionCommand, made_item_settings: AdminMadeItemSettings
    ) -> str:
        """The status the predecessor gets. The web follows the admin setting
        and takes the request's value only while the setting is "ask"; PDM
        ingest passes its own setting as the system user."""
        configured = made_item_settings.revision_predecessor_status_web
        if actor.is_systemuser or configured == _ASK:
            return cmd.predecessor_status
        return configured

    @staticmethod
    def _resolve_next_revision(
        cmd: CreateMadeItemRevisionCommand,
        newest: MadeItem,
        made_item_settings: AdminMadeItemSettings,
    ) -> str:
        """An explicit revision (PDM ingest) skips the increment; the web
        always increments."""
        if cmd.revision is not None:
            return cmd.revision
        return revision_scheme.next_revision(
            newest.revision, made_item_settings.revision_skip_ambiguous_letters
        )

    async def _write_revision(
        self,
        actor: User,
        source: MadeItem,
        cmd: CreateMadeItemRevisionCommand,
        pn: str | None,
        next_rev: str,
        predecessor_status: str,
        data_source: str,
        now: datetime,
        inspection_methods_by_id: dict[int, InspectionMethod],
    ) -> MadeItem:
        # Claims the family's number only if it is not registered yet.
        if pn is not None:
            await self._registry.assert_family(pn, "made")

        new_item = MadeItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog(
                [],
                actor.full_name,
                f"Created as revision {next_rev!r}, succeeding item #{source.id}.",
            ),
            archived=False,
            revision=next_rev,
            revision_date=cmd.item.revision_date,
            revision_note=cmd.item.revision_note,
            article_name=cmd.item.article_name,
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource(data_source),
            part_number=pn,
            material=cmd.item.material,
            mass=cmd.item.mass,
            base_size=cmd.item.base_size,
            note=cmd.item.note,
            weblink=cmd.item.weblink,
            files=[],
            creator_id=actor.id,
            approver_id=None,
            bought_item_id=cmd.item.bought_item_id,
            source_item_id=cmd.item.source_item_id,
            article_group_ids=cmd.item.article_group_ids,
            successor_item_id=None,
            changed_by_id=None,
            customer_id=cmd.item.customer_id,
            customer_part_number=cmd.item.customer_part_number,
            customer_revision=cmd.item.customer_revision,
            creator=actor,
        )
        saved = await self._items.save(new_item)

        await build_and_save_processes(
            self._items,
            saved.id,
            cmd.item.processes,
            inspection_methods_by_id,
            actor.id,
            now,
        )

        # Predecessor: status move with the successor the catalogue rule
        # couples to it, changelog line on both rows.
        old_successor = source.successor_item_id
        new_status = MadeItemCatalogueStatus(predecessor_status)
        replaced = new_status == MadeItemCatalogueStatus.REPLACED
        source.successor_item_id = assert_catalogue_status_change(
            CatalogueStatusChange(
                family="made item",
                item_id=source.id,
                old_status=source.status,
                old_successor_id=old_successor,
                new_status=new_status,
                requested_successor_id=saved.id if replaced else None,
            ),
            SuccessorFacts(id=saved.id, archived=False),
        )
        source.status = new_status
        source.changed = now
        source.changed_by_id = actor.id
        source.changes = self._predecessor_changelog(
            actor, source.changes, saved.id, next_rev, predecessor_status, old_successor
        )
        await self._items.save(source)

        await self._bus.publish(
            MadeItemCreated(
                item_id=saved.id,
                article_name=saved.article_name,
                creator_id=saved.creator_id,
            )
        )
        return saved

    @staticmethod
    def _predecessor_changelog(
        actor: User,
        changes: list[str],
        new_item_id: int,
        next_rev: str,
        predecessor_status: str,
        old_successor: int | None,
    ) -> list[str]:
        """The predecessor's changelog lines: the supersession, a successor
        the status no longer allows, and an override by PDM ingest of a
        successor a person had set."""
        changes = append_changelog(
            changes,
            actor.full_name,
            f"Superseded by revision {next_rev!r} (item #{new_item_id}); "
            f"status set to {predecessor_status!r}.",
        )
        if old_successor is None or old_successor == new_item_id:
            return changes
        if predecessor_status != MadeItemCatalogueStatus.REPLACED.value:
            return append_changelog(
                changes,
                actor.full_name,
                f"Successor item #{old_successor} cleared; only a replaced item names a successor.",
            )
        if actor.is_systemuser:
            return append_changelog(
                changes,
                actor.full_name,
                f"Successor changed from item #{old_successor} to the new revision by PDM revise.",
            )
        return changes

    async def execute(
        self, actor: User, item_id: int, cmd: CreateMadeItemRevisionCommand
    ) -> MadeItemResult:
        prepared = await self.prepare(actor, item_id, cmd)

        # One attempt only, because `source` is already persisted, but the
        # wrapper also catches the conflict assert_family raises on flush.
        saved = await commit_with_number_retry(self._uow, prepared.write, attempts=1)
        saved = await self._items.get_by_id(saved.id) or saved

        log.info(
            f"Created revision {prepared.next_revision!r} of made-item "
            f"catalogue item #{prepared.predecessor_id} as new item #{saved.id}."
        )

        return MadeItemMapper.to_result(saved)
