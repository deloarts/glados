"""
A format a product (machine) produces, such as "Pipe clamp 60" or
"Pipe clamp 80". A product's flow sequences give a value per variant
where it differs, such as a stroke per pipe clamp size. Variants are
edited as one ordered list per product; one taken out of the list is
archived, never deleted, because sequences refer to it by id.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductVariant(Entity):
    product_id: int
    name: str
    sort_order: int
    archived: bool = False
