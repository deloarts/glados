"""
What other modules read of Catalogue: narrow query protocols over its
repositories, which the repositories satisfy as they are, and the filters
they take. Writes go through Catalogue's use cases.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.entities.part_number_registry import UnregisteredPartNumber
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.ports.outbound.repositories.labeled_catalogue_filter import (
    LabeledCatalogueFilterDto,
)


@dataclass
class ArticleGroupFilterDto(LabeledCatalogueFilterDto):
    """The list filter for article groups."""


@dataclass
class BoughtItemFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    status: str | None = None
    order_code_1: str | None = None
    order_code_2: str | None = None
    gtin: str | None = None
    ean: str | None = None
    tariff_number: str | None = None
    article_name: str | None = None
    article_group_id: int | None = None
    product_family_id: int | None = None
    data_source: str | None = None
    part_number: str | None = None
    mass: int | None = None
    note: str | None = None
    weblink: str | None = None
    successor_item_id: int | None = None
    manufacturer_id: int | None = None
    manufacturer_name: str | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    creator_full_name: str | None = None
    approver_id: int | None = None
    include_archived: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    changed_from: datetime | None = None
    changed_to: datetime | None = None
    order_by: str | None = None
    order_dir: str | None = None


@dataclass
class MadeItemFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    status: str | None = None
    article_name: str | None = None
    article_group_id: int | None = None
    data_source: str | None = None
    part_number: str | None = None
    revision: str | None = None
    material: str | None = None
    mass: int | None = None
    note: str | None = None
    weblink: str | None = None
    successor_item_id: int | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    customer_id: int | None = None
    creator_id: int | None = None
    creator_full_name: str | None = None
    approver_id: int | None = None
    include_archived: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    changed_from: datetime | None = None
    changed_to: datetime | None = None
    # Keeps only the newest row of each part-number family (sorted by
    # highest (len(revision), revision), with ties broken by created desc,
    # then id desc), via a `row_number() over (partition by part_number
    # ...)` window in the repository. Rows with a NULL part_number have no
    # family to rank against and always pass.
    latest_only: bool | None = None
    order_by: str | None = None
    order_dir: str | None = None


@dataclass
class ProductFamilyFilterDto(LabeledCatalogueFilterDto):
    """The list filter for product families."""


@dataclass
class SupplierFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    name: str | None = None
    legal_name: str | None = None
    vat_id: str | None = None
    level: str | None = None
    address: str | None = None
    country: str | None = None
    email: str | None = None
    capability_id: int | None = None
    article_group_id: int | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    include_archived: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    changed_from: datetime | None = None
    changed_to: datetime | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IArticleGroupQueries(Protocol):
    async def get_by_ids(self, ids: list[int]) -> list[ArticleGroup]:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_multi(self, filters: ArticleGroupFilterDto) -> tuple[int, list[ArticleGroup]]: ...


@runtime_checkable
class IBoughtItemQueries(Protocol):
    async def get_by_id(self, id: int) -> BoughtItem | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None: ...

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        """Batch counterpart to get_by_part_number's existence check:
        which of `part_numbers` have a live (non-archived) row, without
        fetching the rows themselves. Used by reconcile_pdm_vault's
        registry cross-check, which only needs presence, not the row
        itself."""
        ...

    async def get_by_gtin(self, gtin: str) -> BoughtItem | None:
        """Live (non-archived) rows only, matches the scope of
        `uq_bought_item_gtin_active`."""
        ...

    async def find_by_order_code(self, manufacturer_id: int, order_code: str) -> list[BoughtItem]:
        """Live rows of `manufacturer_id` whose order_code_1 equals
        `order_code` in the comparison form of
        domain.services.order_code.normalize_order_code."""
        ...

    async def find_by_edp_part_id(self, edp_part_id: int) -> list[BoughtItem]:
        """Live rows linked to this EPLAN Data Portal part."""
        ...

    async def find_by_ean(self, ean: str) -> list[BoughtItem]:
        """Live rows with this EAN; unlike the GTIN, an EAN is not unique."""
        ...

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        """The one non-archived row identified by (vault_id, pdm_file_id);
        uq_bought_item_pdm_file makes that pair unique."""
        ...

    async def find_claim_candidate(
        self,
        *,
        gtin: str | None,
        manufacturer_id: int | None,
        order_code_1: str | None,
    ) -> BoughtItem | None:
        """Finds the single non-archived row without a PDM link (web- or
        add-in-created) a PDM file should claim on first sight
        (docs/reference/field-ownership.md sections 1 and 3): an exact `gtin` match first,
        falling back to `manufacturer_id` + `order_code_1` only when no
        gtin is given. Returns None when nothing matches or more than one
        row does, since an ambiguous match is never claimed automatically."""
        ...

    async def get_multi(self, filters: BoughtItemFilterDto) -> tuple[int, list[BoughtItem]]: ...


@runtime_checkable
class IContactQueries(Protocol):
    async def get_by_id(self, id: int) -> Contact | None:
        """Regardless of `archived`, links must resolve."""
        ...

    async def get_by_ids(self, ids: list[int]) -> list[Contact]:
        """Archived rows included, in no particular order."""
        ...

    async def get_mail_contacts_of_customer(self, customer_id: int) -> list[Contact]:
        """The live contacts of a customer with an e-mail address, by name."""
        ...


@runtime_checkable
class ICustomerQueries(Protocol):
    async def get_by_id(self, id: int) -> Customer | None:
        """Regardless of `archived`, references must resolve."""
        ...


@runtime_checkable
class IFabricationMethodQueries(Protocol):
    async def get_by_id(self, id: int) -> FabricationMethod | None:
        """Regardless of `archived`, references must resolve."""
        ...


@runtime_checkable
class IInspectionMethodQueries(Protocol):
    async def get_by_id(self, id: int) -> InspectionMethod | None:
        """Regardless of `archived`, references must resolve."""
        ...


@runtime_checkable
class IItemPictureQueries(Protocol):
    async def get_by_item(self, kind: ItemKind, item_id: int) -> list[ItemPicture]: ...

    async def get_by_items(self, kind: ItemKind, item_ids: list[int]) -> list[ItemPicture]:
        """The pictures of many items in one query, for a table of
        thumbnails."""
        ...

    async def get_by_source(
        self, kind: ItemKind, item_id: int, source: ItemPictureSource
    ) -> ItemPicture | None: ...


@runtime_checkable
class IMadeItemFileQueries(Protocol):
    async def get_by_item_id_and_category(
        self, item_id: int, category: MadeItemFileCategory
    ) -> list[MadeItemFile]:
        """The item's files of one category, which for a singleton category
        such as the drawing is at most one."""
        ...


@runtime_checkable
class IMadeItemQueries(Protocol):
    async def get_by_id(self, id: int) -> MadeItem | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        """All non-archived rows sharing `part_number`: a family's
        revisions. Order is not guaranteed to any particular scheme;
        callers needing "newest first" apply that sort key themselves."""
        ...

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        """Batch counterpart to get_revisions' existence check: which of
        `part_numbers` have at least one non-archived row, without
        fetching the rows themselves. Used by reconcile_pdm_vault's
        registry cross-check, which only needs presence, not the
        family's contents."""
        ...

    async def get_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> MadeItem | None:
        """The one non-archived row identified by the (part_number,
        revision) pair `uq_made_item_part_number_revision` makes
        unique."""
        ...

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        """Every non-archived revision row of the PDM file identified by
        (vault_id, pdm_file_id), newest revision first (same ordering as
        get_multi's latest_only window: revision_scheme.sort_key, ties
        broken by created desc, id desc). Used by ingest to find the
        current newest row of a part and decide new-revision vs.
        update-in-place."""
        ...

    async def get_multi(self, filters: MadeItemFilterDto) -> tuple[int, list[MadeItem]]: ...


@runtime_checkable
class IPartNumberRegistryQueries(Protocol):
    async def owner_of(self, part_number: str) -> PartNumberRegistryEntry | None:
        """The registry row for `part_number`, without claiming anything, so it is
        safe outside a write transaction. ValidatePdmPayload's dry run uses it to
        report a number held by the other catalogue."""
        ...

    async def all_entries(self) -> list[PartNumberRegistryEntry]:
        """Every registry row, unpaged, which is fine at vault scale. Read-only;
        ReconcilePdmVault uses it to find orphaned claims that no live item
        carries."""
        ...

    async def find_unregistered_holders(self) -> list[UnregisteredPartNumber]:
        """Every part number a made or bought item carries, archived rows and
        every revision included, whose registry row is missing or names the
        other catalogue, one per number and catalogue, ordered by number.
        Read-only; the lifecycle drift report lists them."""
        ...


@runtime_checkable
class IProductFamilyQueries(Protocol):
    async def get_multi(
        self, filters: ProductFamilyFilterDto
    ) -> tuple[int, list[ProductFamily]]: ...


@runtime_checkable
class ISourceItemQueries(Protocol):
    async def get_by_id(self, id: int) -> SourceItem | None:
        """Regardless of `archived`, references must resolve."""
        ...


@runtime_checkable
class ISupplierQueries(Protocol):
    async def get_by_id(self, id: int) -> Supplier | None:
        """Resolves regardless of `archived`, since references must resolve."""
        ...

    async def get_multi(self, filters: SupplierFilterDto) -> tuple[int, list[Supplier]]: ...
