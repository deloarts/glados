"""
The row-level pieces of the bought-item batch create: the values a row
resolves to, the shape checks, how a Data Portal draft and the file are
merged (the portal wins for every field it supplies, the file fills the
rest, every disagreement is reported), the divergences of an existing item
and the keys that find a duplicate row. Private to batch_create_items.py.
"""

import math
import re
from dataclasses import dataclass
from dataclasses import field

from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.policies.order_code import normalize_order_code
from src.modules.external_data.application.dto.bought_item_import_dto import (
    BatchBoughtItemDivergence,
)
from src.modules.external_data.application.dto.bought_item_import_dto import (
    BatchBoughtItemDivergenceField,
)
from src.modules.external_data.application.dto.bought_item_import_dto import (
    BatchBoughtItemPortalDifference,
)
from src.modules.external_data.application.dto.bought_item_import_dto import (
    BatchBoughtItemPortalField,
)
from src.modules.external_data.application.dto.bought_item_import_dto import BatchBoughtItemRowInput
from src.modules.external_data.application.dto.bought_item_import_dto import EdpPartSummary
from src.modules.external_data.application.services.edp_item_draft import EdpItemDraft
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.platform.application.services.import_text import norm

_NAME_SEPARATOR = re.compile(r"[;,]")


def text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def names(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [name.strip() for name in _NAME_SEPARATOR.split(raw) if name.strip()]


@dataclass
class NameIndex:
    """Normalised name to the ids carrying it; two ids under one name make
    that name ambiguous. A row may be listed under several names, such as
    the names of an article group in each language, and is kept once per
    name."""

    ids_by_name: dict[str, list[int]] = field(default_factory=dict)

    @classmethod
    def of(cls, rows: list[tuple[int, str]]) -> "NameIndex":
        index = cls()
        for row_id, name in rows:
            ids = index.ids_by_name.setdefault(norm(name), [])
            if row_id not in ids:
                ids.append(row_id)
        return index

    def lookup(self, name: str) -> list[int]:
        return self.ids_by_name.get(norm(name), [])


@dataclass
class RowValues:
    """What a row creates, after the file, the portal and the name lookups
    are combined."""

    article_name: str | None
    order_code_1: str | None
    order_code_2: str | None
    gtin: str | None
    ean: str | None
    tariff_number: str | None
    mass: int | None
    note: str | None
    weblink: str | None
    part_number: str | None
    manufacturer_id: int | None = None
    article_group_ids: list[int] = field(default_factory=list)
    product_family_id: int | None = None
    product_family_name: str | None = None
    edp_part_id: int | None = None

    @classmethod
    def of(cls, row: BatchBoughtItemRowInput) -> "RowValues":
        return cls(
            article_name=text(row.article_name),
            order_code_1=text(row.order_code_1),
            order_code_2=text(row.order_code_2),
            gtin=text(row.gtin),
            ean=text(row.ean),
            tariff_number=text(row.tariff_number),
            mass=None if row.mass is None else int(row.mass),
            note=text(row.note),
            weblink=text(row.weblink),
            part_number=text(row.part_number),
            product_family_name=text(row.product_family_name),
        )

    def command(self) -> CreateBoughtItemCommand:
        assert self.manufacturer_id is not None
        return CreateBoughtItemCommand(
            order_code_1=self.order_code_1 or "",
            order_code_2=self.order_code_2,
            gtin=self.gtin,
            ean=self.ean,
            tariff_number=self.tariff_number,
            article_name=self.article_name or "",
            article_group_ids=self.article_group_ids,
            part_number=self.part_number,
            mass=self.mass,
            note=self.note,
            weblink=self.weblink,
            manufacturer_id=self.manufacturer_id,
            product_family_id=self.product_family_id,
            edp_part_id=self.edp_part_id,
        )

    def keys(self) -> set[str]:
        """What identifies the item within one file."""
        keys = {f"code:{self.manufacturer_id}:{normalize_order_code(self.order_code_1)}"}
        if self.gtin:
            keys.add(f"gtin:{norm(self.gtin)}")
        if self.ean:
            keys.add(f"ean:{norm(self.ean)}")
        if self.edp_part_id is not None:
            keys.add(f"edp:{self.edp_part_id}")
        return keys


def mass_error(row: BatchBoughtItemRowInput) -> str | None:
    if row.mass is not None and (
        not math.isfinite(row.mass) or row.mass < 0 or row.mass != int(row.mass)
    ):
        return "Mass must be a whole number of grams, 0 or more."
    return None


def file_shape_errors(row: BatchBoughtItemRowInput) -> list[str]:
    """A row created from the file alone needs its name, code and maker."""
    errors: list[str] = []
    if not text(row.order_code_1):
        errors.append("Order code is required.")
    if not text(row.article_name):
        errors.append("Article name is required.")
    if not text(row.manufacturer_name):
        errors.append("Manufacturer is required.")
    if error := mass_error(row):
        errors.append(error)
    return errors


def lookup_shape_errors(row: BatchBoughtItemRowInput) -> list[str]:
    """A row looked up in the portal needs something to look it up by."""
    errors: list[str] = []
    if row.edp_part_id is None and not text(row.order_code_1) and not text(row.edp_part_number):
        errors.append("An order code or EPLAN part number is required.")
    if error := mass_error(row):
        errors.append(error)
    return errors


def lookup_key(row: BatchBoughtItemRowInput) -> str | None:
    """The number a row is looked up by: its EPLAN part number, else its
    order code. None for a row with a pinned part or none to look up."""
    if row.edp_part_id is not None:
        return None
    return text(row.edp_part_number) or text(row.order_code_1)


def apply_draft(
    values: RowValues, draft: EdpItemDraft, manufacturer_name: str | None
) -> list[BatchBoughtItemPortalDifference]:
    """Lets the portal win for the fields it supplies and returns where the
    file said something else."""
    differences: list[BatchBoughtItemPortalDifference] = []

    def take(name: BatchBoughtItemPortalField, portal: str | None, file: str | None) -> str | None:
        if portal is None:
            return file
        if file is not None and norm(file) != norm(portal):
            differences.append(
                BatchBoughtItemPortalDifference(field=name, portal_value=portal, file_value=file)
            )
        return portal

    values.article_name = take("article_name", draft.article_name, values.article_name)
    values.order_code_1 = take("order_code_1", draft.order_code_1, values.order_code_1)
    values.order_code_2 = take("order_code_2", draft.order_code_2, values.order_code_2)
    values.ean = take("ean", draft.ean, values.ean)
    values.weblink = take("weblink", draft.weblink, values.weblink)
    if manufacturer_name and draft.manufacturer_name:
        take("manufacturer", draft.manufacturer_name, manufacturer_name)
    if draft.product_family_id is not None:
        take("product_family", draft.product_family_name, values.product_family_name)
        values.product_family_id = draft.product_family_id
    values.manufacturer_id = draft.manufacturer_id
    values.edp_part_id = draft.edp_part_id
    return differences


def existing_divergences(values: RowValues, item: BoughtItem) -> list[BatchBoughtItemDivergence]:
    """Where the row's values differ from an item already in the catalogue."""
    pairs: list[tuple[BatchBoughtItemDivergenceField, str | None, str | None]] = [
        ("article_name", item.article_name, values.article_name),
        ("order_code_2", item.order_code_2, values.order_code_2),
        ("gtin", item.gtin, values.gtin),
        ("ean", item.ean, values.ean),
        ("tariff_number", item.tariff_number, values.tariff_number),
        (
            "mass",
            None if item.mass is None else str(item.mass),
            None if values.mass is None else str(values.mass),
        ),
        ("weblink", item.weblink, values.weblink),
    ]
    divergences = [
        BatchBoughtItemDivergence(field=name, db_value=db, file_value=file)
        for name, db, file in pairs
        if file is not None and norm(file) != norm(db)
    ]
    if values.product_family_id is not None and values.product_family_id != item.product_family_id:
        divergences.append(
            BatchBoughtItemDivergence(
                field="product_family",
                db_value=item.product_family.name if item.product_family else None,
                file_value=values.product_family_name,
            )
        )
    return divergences


def summary(part: EdpPart, language: str) -> EdpPartSummary:
    return EdpPartSummary(
        part_id=part.part_id,
        part_number=part.part_number,
        order_number=part.order_number,
        type_number=part.type_number,
        designation=part.text_in(language),
        manufacturer_code=part.manufacturer_code,
        manufacturer_name=part.manufacturer_name,
        product_family_name=part.product_family_name,
        picture_url=part.picture_url,
        part_page_url=part.part_page_url,
    )
