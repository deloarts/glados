"""
Shared ORM-to-entity mapping helpers for product families, used by every
repository that loads them.

Each mapper has a matching loader function returning the eager-load options
for every relationship it dereferences. They are built on first call and
cached, not at module scope, because constructing a loader option configures
the mapper registry, which fails while model modules are still importing.
"""

from functools import lru_cache

from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.product_family_model import (
    ProductFamilyOrmModel,
)
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user


@lru_cache(maxsize=1)
def product_family_load_options() -> tuple[ORMOption, ...]:
    return (load_user(ProductFamilyOrmModel.creator), load_user(ProductFamilyOrmModel.changed_by))


def product_family_orm_to_entity(orm: ProductFamilyOrmModel) -> ProductFamily:
    return ProductFamily(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=orm.name,
        label_color=orm.label_color,
        label_font_color=orm.label_font_color,
        description=orm.description,
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def product_family_ref_orm_to_entity(orm: ProductFamilyOrmModel) -> ProductFamily:
    """A product family as an item embeds it: the row's own columns only,
    without the creator and changer, so an item query loads just the family row."""
    return ProductFamily(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=orm.name,
        label_color=orm.label_color,
        label_font_color=orm.label_font_color,
        description=orm.description,
        sort_order=orm.sort_order,
        creator_id=orm.creator_id,
        creator=None,
        changed_by_id=orm.changed_by_id,
        changed_by=None,
    )
