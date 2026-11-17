"""Updates a made item's editable fields, enforcing PDM ownership, the
revision policy and part number rules. Status and successor are checked
together (src/modules/catalogue/domain/policies/catalogue_item_status.py), and a status change
publishes MadeItemStatusChanged."""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemCommand
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.application.services.catalogue_successor import resolve_successor
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.errors import MadeItemFieldRequiresRevisionError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import MadeItemPartNumberNotEditableError
from src.modules.catalogue.domain.errors import PdmSuccessorRequiresReplacedStatusError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.events.made_item_events import MadeItemStatusChanged
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.item_field_ownership import web_blocked_changes
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import newest_of
from src.modules.catalogue.domain.policies.pdm_ownership import assert_cad_row_writable
from src.modules.catalogue.domain.policies.pdm_ownership import assert_part_number_not_pdm_reserved
from src.modules.catalogue.domain.policies.pdm_ownership import blocked_pdm_owned_changes
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_locked_fields
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.cad_source_port import CadPolicy
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
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.part_number_registry import (
    IPartNumberRegistry,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# The fields an older revision may still change.
_NEWEST_EXEMPT_FIELDS = frozenset({"status", "successor_item_id"})

# Fields for the newest-only check; article groups compare as a set.
_SCALAR_FIELDS = (
    "revision_date",
    "revision_note",
    "article_name",
    "status",
    "part_number",
    "material",
    "mass",
    "base_size",
    "note",
    "weblink",
    "bought_item_id",
    "source_item_id",
    "customer_id",
    "customer_part_number",
    "customer_revision",
    "successor_item_id",
)

_CUSTOMER_FIELDS = ("customer_id", "customer_part_number", "customer_revision")


def _changed_fields(item: MadeItem, cmd: UpdateMadeItemCommand) -> set[str]:
    changed = {f for f in _SCALAR_FIELDS if getattr(item, f) != getattr(cmd, f)}
    if set(item.article_group_ids) != set(cmd.article_group_ids):
        changed.add("article_group_ids")
    return changed


class UpdateMadeItem:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        article_group_repo: IArticleGroupRepository,
        bought_item_repo: IBoughtItemRepository,
        source_item_repo: ISourceItemRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        *,
        cad_source: ICadSource,
        customer_repo: ICustomerRepository,
        part_number_registry: IPartNumberRegistry,
        uow: IUnitOfWork,
        # None only for unit tests that predate the status event; the deps
        # factory always passes the transactional bus.
        event_bus: IEventBus | None = None,
    ) -> None:
        self._items = made_item_repo
        self._article_groups = article_group_repo
        self._bought_items = bought_item_repo
        self._source_items = source_item_repo
        self._admin_settings = admin_settings_repo
        self._cad = cad_source
        self._customers = customer_repo
        self._registry = part_number_registry
        self._uow = uow
        self._bus = event_bus

    async def execute(
        self, actor: User, item_id: int, cmd: UpdateMadeItemCommand
    ) -> MadeItemResult:
        MadeItemCatalogueRules.assert_can_update(actor)

        await self._items.lock_for_update(item_id)
        item = found_or_raise(
            await self._items.get_by_id(item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )
        assert_edit_version(item, cmd.expected_edit_version, what=f"Catalogue item #{item.id}")

        MadeItemCatalogueRules.assert_at_most_one_material_source(
            cmd.bought_item_id, cmd.source_item_id
        )

        made_item_settings = await self._admin_settings.get_made_items()
        cad = await self._cad.policy()

        enforce = self._assert_pdm_ownership_allows(actor, item, cmd, cad)
        await self._assert_newest_revision_editable(item, cmd, made_item_settings)
        self._assert_revision_policy_allows(item, cmd, made_item_settings)
        await self._assert_references_exist(item, cmd)
        # From here on the command carries the successor the item keeps.
        cmd = cmd.model_copy(
            update={"successor_item_id": await self._resolve_successor(item, cmd, enforce)}
        )

        if cmd.part_number == item.part_number:
            saved = await self._apply_changes(item, actor, cmd)
            await self._uow.commit()
        else:
            saved = await self._save_with_renumber(
                actor, item, cmd, made_item_settings, cad.connected
            )

        log.info(f"Updated made-item catalogue item {saved.article_name!r}, ID={saved.id}.")
        result = MadeItemMapper.to_result(saved)
        # The same `enforce` as the write check, so the two never disagree.
        result.pdm_locked_fields = pdm_locked_fields(
            kind="made", enforce=enforce, item_data_source=saved.data_source
        )
        return result

    def _assert_pdm_ownership_allows(
        self,
        actor: User,
        item: MadeItem,
        cmd: UpdateMadeItemCommand,
        cad: CadPolicy,
    ) -> bool:
        """Refuses changes to PDM-owned fields of a CAD row while ownership
        is enforced, renumbering included. Returns `enforce`."""
        enforce = cad.enforces_ownership_for(actor)
        assert_cad_row_writable(
            enforce=enforce,
            item_data_source=item.data_source,
            blocked=blocked_pdm_owned_changes("made", item, cmd.model_dump()),
        )

        # Status is PDM-owned here, so a successor needs the row to be
        # `replaced` already; clearing one is always allowed.
        if (
            enforce
            and item.data_source == DataSource.CAD.value
            and cmd.successor_item_id is not None
            and cmd.successor_item_id != item.successor_item_id
            and item.status != MadeItemCatalogueStatus.REPLACED.value
        ):
            raise PdmSuccessorRequiresReplacedStatusError(
                f"Catalogue item #{item.id}: status is managed by PDM; move the file to a "
                "replaced state before assigning a successor here."
            )
        return enforce

    async def _assert_newest_revision_editable(
        self, item: MadeItem, cmd: UpdateMadeItemCommand, made_item_settings: AdminMadeItemSettings
    ) -> None:
        """Only the newest revision is editable, except status and successor."""
        if made_item_settings.revision_only_newest_editable and item.part_number is not None:
            siblings = await self._items.get_revisions(item.part_number)
            if newest_of(siblings).id != item.id:
                changed = _changed_fields(item, cmd)
                if not changed <= _NEWEST_EXEMPT_FIELDS:
                    raise MadeItemNotNewestRevisionError(
                        f"Catalogue item #{item.id} is not the newest revision of part "
                        f"number {item.part_number!r}; only status changes are allowed. "
                        'Use "New revision" instead.'
                    )

    def _assert_revision_policy_allows(
        self, item: MadeItem, cmd: UpdateMadeItemCommand, made_item_settings: AdminMadeItemSettings
    ) -> None:
        """On a WEB item, revision-policy fields only change through "New
        revision"."""
        if item.data_source == DataSource.WEB.value:
            blocked = web_blocked_changes(item, cmd, made_item_settings.revision_field_policy)
            if blocked:
                raise MadeItemFieldRequiresRevisionError(
                    f"Catalogue item #{item.id}: changing {sorted(blocked)} requires a new "
                    "revision."
                )

    async def _assert_references_exist(self, item: MadeItem, cmd: UpdateMadeItemCommand) -> None:
        """Checks the references the write names. A material reference is
        checked only when it changes, so a material that turned inactive
        later does not lock the item's other edits, its retirement included."""
        if cmd.article_group_ids:
            found = await self._article_groups.get_by_ids(cmd.article_group_ids)
            if len(found) != len(set(cmd.article_group_ids)):
                missing = set(cmd.article_group_ids) - {g.id for g in found}
                raise ArticleGroupNotFoundError(f"Article group(s) {missing} not found.")

        if cmd.bought_item_id is not None and cmd.bought_item_id != item.bought_item_id:
            bought_item = found_or_raise(
                await self._bought_items.get_by_id(cmd.bought_item_id),
                BoughtItemNotFoundError,
                f"Bought item #{cmd.bought_item_id} not found.",
            )
            BoughtItemCatalogueRules.assert_item_active(bought_item)

        if cmd.source_item_id is not None and cmd.source_item_id != item.source_item_id:
            source_item = found_or_raise(
                await self._source_items.get_by_id(cmd.source_item_id),
                SourceItemNotFoundError,
                f"Source item #{cmd.source_item_id} not found.",
            )
            SourceItemCatalogueRules.assert_item_active(source_item)

        await self._assert_customer_data_valid(item, cmd)

    async def _assert_customer_data_valid(self, item: MadeItem, cmd: UpdateMadeItemCommand) -> None:
        """Checks the customer data only when the write changes it, so a CAD
        row that PDM filled in incompletely keeps its other edits open. The
        customer only has to exist, archived or not."""
        if all(getattr(item, f) == getattr(cmd, f) for f in _CUSTOMER_FIELDS):
            return
        MadeItemCatalogueRules.assert_customer_data_complete(
            cmd.customer_id, cmd.customer_part_number, cmd.customer_revision
        )
        if cmd.customer_id is not None and cmd.customer_id != item.customer_id:
            found_or_raise(
                await self._customers.get_by_id(cmd.customer_id),
                CustomerNotFoundError,
                f"Customer #{cmd.customer_id} not found.",
            )

    async def _resolve_successor(
        self, item: MadeItem, cmd: UpdateMadeItemCommand, enforce: bool
    ) -> int | None:
        """The successor the item keeps, after the status rule accepted the
        write. On an enforced CAD row PDM owns the status."""
        return await resolve_successor(
            CatalogueStatusChange(
                family="made item",
                item_id=item.id,
                old_status=item.status,
                old_successor_id=item.successor_item_id,
                new_status=MadeItemCatalogueStatus(cmd.status),
                requested_successor_id=cmd.successor_item_id,
                status_owned_by_pdm=enforce and item.data_source == DataSource.CAD.value,
            ),
            self._items.get_by_id,
        )

    async def _apply_changes(
        self, target: MadeItem, actor: User, cmd: UpdateMadeItemCommand
    ) -> MadeItem:
        changelog_entry = diff_command(target, cmd)
        old_status = target.status

        target.revision_date = cmd.revision_date
        target.revision_note = cmd.revision_note
        target.article_name = cmd.article_name
        target.article_group_ids = cmd.article_group_ids
        target.status = MadeItemCatalogueStatus(cmd.status)
        target.part_number = cmd.part_number
        target.material = cmd.material
        target.mass = cmd.mass
        target.base_size = cmd.base_size
        target.note = cmd.note
        target.weblink = cmd.weblink
        target.bought_item_id = cmd.bought_item_id
        target.source_item_id = cmd.source_item_id
        target.customer_id = cmd.customer_id
        target.customer_part_number = cmd.customer_part_number
        target.customer_revision = cmd.customer_revision
        target.successor_item_id = cmd.successor_item_id
        target.changed = now_utc()
        target.changed_by_id = actor.id
        target.changes = append_changelog(target.changes, actor.full_name, changelog_entry)
        saved = await self._items.save(target)
        await self._publish_status_change(actor, old_status, saved)
        return saved

    async def _publish_status_change(self, actor: User, old_status: str, saved: MadeItem) -> None:
        if self._bus is None or saved.status == old_status:
            return
        await self._bus.publish(
            MadeItemStatusChanged(
                item_id=saved.id,
                article_name=saved.article_name,
                old_status=MadeItemCatalogueStatus(old_status),
                new_status=MadeItemCatalogueStatus(saved.status),
                actor_id=actor.id,
            )
        )

    async def _save_with_renumber(
        self,
        actor: User,
        item: MadeItem,
        cmd: UpdateMadeItemCommand,
        made_item_settings: AdminMadeItemSettings,
        pdm_enabled: bool,
    ) -> MadeItem:
        if not made_item_settings.part_number_editable:
            raise MadeItemPartNumberNotEditableError(
                f"Catalogue item #{item.id}'s part number cannot be changed."
            )

        new_pn = cmd.part_number
        old_pn = item.part_number

        if new_pn is not None:
            assert_part_number_not_pdm_reserved(
                new_pn, made_item_settings.pdm_part_number_pattern, enabled=pdm_enabled
            )

        # One attempt only, because the family is already persisted, but the
        # wrapper also maps conflicts the registry raises on flush to a 409.
        async def write() -> MadeItem:
            return await self._write_renumbered(item, actor, cmd, new_pn, old_pn)

        return await commit_with_number_retry(self._uow, write, attempts=1)

    async def _write_renumbered(
        self,
        item: MadeItem,
        actor: User,
        cmd: UpdateMadeItemCommand,
        new_pn: str | None,
        old_pn: str | None,
    ) -> MadeItem:
        # The whole family, archived rows included, moves together, since
        # the (part_number, revision) index covers every row.
        family = await self._items.get_family(old_pn) if old_pn is not None else [item]

        if new_pn is not None:
            # Claim the new number before save, in the same transaction.
            await self._registry.claim(new_pn, "made")
            # A friendly backstop; claim() already blocks collisions.
            for sibling in family:
                existing = await self._items.get_by_part_number_and_revision(
                    new_pn, sibling.revision
                )
                if existing is not None and existing.id != sibling.id:
                    raise MadeItemPartNumberDuplicateError(
                        f"Part number {new_pn!r} is already in use for revision "
                        f"{sibling.revision!r}."
                    )

        for sibling in family:
            if sibling.id == item.id:
                continue
            sibling.part_number = new_pn
            await self._items.save(sibling)

        result = await self._apply_changes(item, actor, cmd)

        # Only after every row moved, or the old number still looks in use.
        if old_pn is not None:
            await self._registry.release_if_unused(old_pn)

        return result
