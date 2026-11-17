"""
In-memory fake repositories and gateways shared by the ingest_pdm_file
test modules (and by test_validate_pdm_payload.py, which reuses several
directly).
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from types import SimpleNamespace

from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmTransition
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_pdm_link import UserPdmLink
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.unit.ingest_pdm_file._helpers import make_made_item_settings
from tests.unit.ingest_pdm_file._helpers import make_order_settings
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None):
        self._items: dict[int, MadeItem] = {i.id: i for i in (items or [])}
        self._next_id = max((i.id for i in (items or [])), default=0) + 1
        self._processes: dict[int, object] = {}
        self.raise_on_save: Exception | None = None

    async def get_by_id(self, id: int) -> MadeItem | None:
        return self._items.get(id)

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        return [i for i in self._items.values() if i.part_number == part_number and not i.archived]

    async def get_family(self, part_number: str) -> list[MadeItem]:
        return [i for i in self._items.values() if i.part_number == part_number]

    async def get_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> MadeItem | None:
        return next(
            (
                i
                for i in self._items.values()
                if i.part_number == part_number and i.revision == revision and not i.archived
            ),
            None,
        )

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        rows = [
            i
            for i in self._items.values()
            if not i.archived and i.vault_id == vault_id and i.pdm_file_id == pdm_file_id
        ]
        rows.sort(key=lambda i: revision_scheme.sort_key(i.revision), reverse=True)
        return rows

    async def get_multi(self, filters: object) -> tuple[int, list[MadeItem]]:
        raise NotImplementedError

    async def save(self, item: MadeItem) -> MadeItem:
        if self.raise_on_save is not None:
            raise self.raise_on_save
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def delete(self, item: MadeItem) -> None:
        self._items.pop(item.id, None)

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError

    async def get_processes(self, made_item_id: int) -> list:
        return []

    async def get_process_by_id(self, process_id: int):
        return None

    async def save_process(self, process):
        return process

    async def delete_process(self, process) -> None:
        return None

    async def reorder_processes(self, made_item_id: int, ordered_process_ids: list[int]):
        raise NotImplementedError

    async def set_process_groups(self, made_item_id: int, groups: list[list[int]]):
        raise NotImplementedError


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {i.id: i for i in (items or [])}
        self._next_id = max((i.id for i in (items or [])), default=0) + 1
        self.raise_on_save: Exception | None = None

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        return next(
            (i for i in self._items.values() if i.part_number == part_number and not i.archived),
            None,
        )

    async def get_by_gtin(self, gtin: str) -> BoughtItem | None:
        return next((i for i in self._items.values() if i.gtin == gtin and not i.archived), None)

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        return next(
            (
                i
                for i in self._items.values()
                if not i.archived and i.vault_id == vault_id and i.pdm_file_id == pdm_file_id
            ),
            None,
        )

    async def find_claim_candidate(
        self,
        *,
        gtin: str | None,
        manufacturer_id: int | None,
        order_code_1: str | None,
    ) -> BoughtItem | None:
        candidates = [i for i in self._items.values() if not i.archived and i.pdm_file_id is None]
        if gtin:
            matches = [i for i in candidates if i.gtin == gtin]
            return matches[0] if len(matches) == 1 else None
        if manufacturer_id is not None and order_code_1:
            matches = [
                i
                for i in candidates
                if i.manufacturer_id == manufacturer_id and i.order_code_1 == order_code_1
            ]
            return matches[0] if len(matches) == 1 else None
        return None

    async def get_multi(self, filters: object) -> tuple[int, list[BoughtItem]]:
        raise NotImplementedError

    async def save(self, item: BoughtItem) -> BoughtItem:
        if self.raise_on_save is not None:
            raise self.raise_on_save
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def delete(self, item: BoughtItem) -> None:
        self._items.pop(item.id, None)

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError


class FakeArticleGroupRepository:
    def __init__(self, groups: list[ArticleGroup] | None = None):
        self._groups: dict[int, ArticleGroup] = {g.id: g for g in (groups or [])}

    async def get_by_id(self, id: int) -> ArticleGroup | None:
        return self._groups.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[ArticleGroup]:
        return [self._groups[i] for i in ids if i in self._groups]

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(self, filters: object) -> tuple[int, list[ArticleGroup]]:
        raise NotImplementedError

    async def save(self, article_group: ArticleGroup) -> ArticleGroup:
        raise NotImplementedError

    async def delete(self, article_group: ArticleGroup) -> None:
        raise NotImplementedError


class FakeSourceItemRepository:
    def __init__(self, items: list[SourceItem] | None = None):
        self._items: dict[int, SourceItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> SourceItem | None:
        return self._items.get(id)


class FakeSupplierRepository:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers: dict[int, Supplier] = {s.id: s for s in (suppliers or [])}

    async def get_by_id(self, id: int) -> Supplier | None:
        return self._suppliers.get(id)


class FakeFabricationMethodRepository:
    async def get_by_id(self, id: int):
        return None


class FakeInspectionMethodRepository:
    async def get_by_id(self, id: int):
        return None


class FakeAdminSettingsRepository:
    def __init__(
        self,
        made_items: AdminMadeItemSettings | None = None,
        orders: AdminOrderSettings | None = None,
        pdm: AdminPdmSettings | None = None,
    ):
        self._made_items = made_items or make_made_item_settings()
        self._orders = orders or make_order_settings()
        self._pdm = pdm or make_pdm_settings()
        # The tenant's timezone, the seeded default, whose day a PDM
        # transition counts on.
        self.default_timezone = "Europe/Vienna"

    async def get_general(self) -> SimpleNamespace:
        return SimpleNamespace(default_timezone=self.default_timezone)

    async def get_made_items(self) -> AdminMadeItemSettings:
        return self._made_items

    async def get_orders(self) -> AdminOrderSettings:
        return self._orders

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm

    async def save_pdm_session(
        self, *, token: str | None, user_id: int | None, obtained_at: datetime | None
    ) -> None:
        self._pdm.session_token = token
        self._pdm.session_user_id = user_id
        self._pdm.session_obtained_at = obtained_at


class FakePdmGateway:
    """Only file_transitions is exercised by IngestPdmFile; authenticate
    backs PdmSessionService's own first call. `transitions_error`, when
    set, is raised by file_transitions to exercise the "attribution
    unavailable" path; always a DomainError subclass, the only kind
    IngestPdmFile catches."""

    def __init__(
        self,
        transitions: list[PdmTransition] | None = None,
        transitions_error: Exception | None = None,
    ) -> None:
        self._transitions = list(transitions or [])
        self._transitions_error = transitions_error
        self.transition_calls: list[tuple[int, int, int]] = []

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        return PdmAuthResult(token="fake-pdm-token", user_id=1)

    async def file_transitions(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmTransition]:
        self.transition_calls.append((file_id, version, folder_id))
        if self._transitions_error is not None:
            raise self._transitions_error
        return list(self._transitions)


class FakePartNumberRegistry:
    def __init__(self, preclaimed: dict[str, str] | None = None) -> None:
        self._entries: dict[str, str] = dict(preclaimed or {})
        self._next_seq = 1
        self.released: list[str] = []

    @property
    def entries(self) -> dict[str, str]:
        """Each claimed part number with the kind it is claimed for, for assertions."""
        return self._entries

    async def owner_of(self, part_number: str) -> "PartNumberRegistryEntry | None":
        kind = self._entries.get(part_number)
        if kind is None:
            return None
        return PartNumberRegistryEntry(
            part_number=part_number, kind=ItemKind(kind), created=date(2026, 1, 1)
        )

    async def claim(self, part_number: str, kind: str) -> None:
        from src.modules.catalogue.domain.errors import PartNumberInUseError

        existing = self._entries.get(part_number)
        if existing is not None:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing!r}."
            )
        self._entries[part_number] = kind

    async def assert_family(self, part_number: str, kind: str) -> None:
        existing = self._entries.get(part_number)
        if existing is None:
            await self.claim(part_number, kind)
            return
        if existing != kind:
            from src.modules.catalogue.domain.errors import PartNumberInUseError

            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing!r}."
            )

    async def release_if_unused(self, part_number: str) -> None:
        self._entries.pop(part_number, None)
        self.released.append(part_number)

    async def next_part_number(self, template: str) -> str:
        value = f"AUTO-{self._next_seq}"
        self._next_seq += 1
        return value


class FakePdmFileSnapshotRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, int], PdmFileSnapshot] = {}
        self._next_id = 1

    async def get_by_file(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None:
        return self._rows.get((vault_id, file_id))

    async def get_by_id(self, id: int) -> PdmFileSnapshot | None:
        return next((r for r in self._rows.values() if r.id == id), None)

    async def find_by_path_suffix(self, vault_id: str, path_suffix: str) -> PdmFileSnapshot | None:
        normalized = path_suffix.lower()
        matches = [
            r
            for r in self._rows.values()
            if r.vault_id == vault_id and normalized.endswith(r.path.lower())
        ]
        if not matches:
            return None
        longest = max(len(r.path) for r in matches)
        best = [r for r in matches if len(r.path) == longest]
        return best[0] if len(best) == 1 else None

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:
        for item in items:
            if item.id == 0:
                item.id = self._next_id
                self._next_id += 1
            self._rows[(item.vault_id, item.file_id)] = item

    async def get_multi(self, filters: object) -> tuple[int, list[PdmFileSnapshot]]:
        raise NotImplementedError

    async def list_conflicts(self, vault_id: str) -> list[PdmFileSnapshot]:
        raise NotImplementedError

    async def save(self, item: PdmFileSnapshot) -> PdmFileSnapshot:
        raise NotImplementedError

    async def counts_by_state(self, vault_id: str) -> dict[str, int]:
        raise NotImplementedError


class FakeUserRepository:
    def __init__(self, system_user: User, extra_users: list[User] | None = None) -> None:
        self._system_user = system_user
        self._by_id = {system_user.id: system_user}
        self._by_username = {system_user.username.lower(): system_user}
        for user in extra_users or []:
            self._by_id[user.id] = user
            self._by_username[user.username.lower()] = user

    async def get_by_username(self, username: str) -> User | None:
        return self._system_user if username == self._system_user.username else None

    async def get_by_id(self, id: int) -> User | None:
        return self._by_id.get(id)

    async def get_by_username_ci(self, username: str) -> User | None:
        return self._by_username.get(username.strip().lower())

    async def get_by_email_ci(self, email: str) -> User | None:
        value = email.strip().lower()
        for user in self._by_id.values():
            if user.email.lower() == value:
                return user
        return None


class FakeUserPdmLinkRepository:
    """Keyed on pdm_user_id, mirroring user_pdm_link_table's unique
    constraint. `pdm_links` maps pdm_user_id -> the Glados user id it
    resolves to, for the releaser-attribution tests below."""

    def __init__(self, pdm_links: dict[int, int] | None = None) -> None:
        self._by_pdm_user_id = {
            pdm_user_id: UserPdmLink(
                id=i,
                user_id=user_id,
                pdm_user_id=pdm_user_id,
                pdm_username="",
                linked_at=datetime.now(UTC),
            )
            for i, (pdm_user_id, user_id) in enumerate((pdm_links or {}).items(), start=1)
        }

    async def get_by_pdm_user_id(self, pdm_user_id: int) -> UserPdmLink | None:
        return self._by_pdm_user_id.get(pdm_user_id)
