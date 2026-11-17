"""
How a part from the EPLAN Data Portal becomes bought-item values, shared by
the create dialog's search, the spreadsheet import and the lookup on an
existing item, so all three fill an item the same way:

- article_name: the designation in the settings' language, else the other
  language, else the description;
- order_code_1: the order number; order_code_2: the type number when it
  differs from the order number. For a manufacturer whose supplier says the
  type number comes first (Festo) the two swap, and a part without a type
  number keeps its order number as order_code_1;
- ean: the part's EAN identcode; weblink: the manufacturer's support page,
  else the part's own Data Portal page;
- manufacturer: the live supplier whose Data Portal code is the part's
  manufacturer code, nothing else (a missing code is reported, never
  guessed from the name);
- product family: the live family named like the part's deepest product
  group, compared without regard to case;
- article groups: the default groups of the Data Portal settings.

The supplier and product family lists are read once per builder, so one
builder serves a whole import.
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.catalogue.domain.policies.order_code import normalize_order_code
from src.modules.catalogue.ports.outbound.catalogue_queries import IProductFamilyQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ProductFamilyFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.platform.application.services.import_text import norm
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.const import MAX_PAGE_SIZE


@dataclass(frozen=True)
class EdpItemDraft:
    edp_part_id: int
    edp_part_number: str
    article_name: str | None
    order_code_1: str | None
    order_code_2: str | None
    ean: str | None
    weblink: str | None
    manufacturer_code: str | None
    manufacturer_name: str | None
    # None when no live supplier carries manufacturer_code.
    manufacturer_id: int | None
    product_family_name: str | None
    # None when no live family is named like product_family_name.
    product_family_id: int | None
    article_group_ids: list[int] = field(default_factory=list)
    picture_url: str | None = None
    part_page_url: str | None = None


def order_codes(part: EdpPart, type_number_first: bool) -> tuple[str | None, str | None]:
    """Order codes 1 and 2 of a part: the order number, then the type number
    unless it is the same code, or the other way round when the manufacturer
    names its parts by type number first."""
    first, second = part.order_number, part.type_number
    if type_number_first and part.type_number:
        first, second = part.type_number, part.order_number
    if second and normalize_order_code(second) == normalize_order_code(first):
        second = None
    return first, second


class EdpDraftBuilder:
    def __init__(
        self,
        settings: AdminEdpSettings,
        supplier_repo: ISupplierQueries,
        product_family_repo: IProductFamilyQueries,
    ) -> None:
        self._settings = settings
        self._suppliers = supplier_repo
        self._families = product_family_repo
        self._supplier_by_code: dict[str, int] | None = None
        self._type_number_first: set[str] = set()
        self._family_by_name: dict[str, int] | None = None

    async def _load(self) -> None:
        if self._supplier_by_code is not None and self._family_by_name is not None:
            return
        suppliers = await fetch_all(
            lambda skip, limit: self._suppliers.get_multi(
                SupplierFilterDto(skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        self._supplier_by_code = {s.edp_code: s.id for s in suppliers if s.edp_code}
        self._type_number_first = {
            s.edp_code for s in suppliers if s.edp_code and s.edp_type_number_first
        }
        families = await fetch_all(
            lambda skip, limit: self._families.get_multi(
                ProductFamilyFilterDto(skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        by_name: dict[str, list[int]] = {}
        for family in families:
            by_name.setdefault(norm(family.name), []).append(family.id)
        self._family_by_name = {name: ids[0] for name, ids in by_name.items() if len(ids) == 1}

    async def draft(self, part: EdpPart) -> EdpItemDraft:
        await self._load()
        assert self._supplier_by_code is not None and self._family_by_name is not None
        code = (part.manufacturer_code or "").upper() or None
        family_name = part.product_family_name
        order_code_1, order_code_2 = order_codes(
            part, code is not None and code in self._type_number_first
        )
        return EdpItemDraft(
            edp_part_id=part.part_id,
            edp_part_number=part.part_number,
            article_name=part.text_in(self._settings.language),
            order_code_1=order_code_1,
            order_code_2=order_code_2,
            ean=part.ean,
            weblink=part.support_url or part.part_page_url,
            manufacturer_code=code,
            manufacturer_name=part.manufacturer_name,
            manufacturer_id=self._supplier_by_code.get(code) if code else None,
            product_family_name=family_name,
            product_family_id=self._family_by_name.get(norm(family_name)) if family_name else None,
            article_group_ids=list(self._settings.default_article_group_ids),
            picture_url=part.picture_url,
            part_page_url=part.part_page_url,
        )
