"""
Shared ORM-to-entity mapping helpers for the catalogue's labeled entities
(article groups, fabrication and inspection methods, source item types),
used by every repository that loads them.

Each mapper has a matching loader function returning the eager-load options
for every relationship it dereferences. They are built on first call and
cached, not at module scope, because constructing a loader option configures
the mapper registry, which fails while model modules are still importing.
"""

from functools import lru_cache

from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.inspection_method_model import (
    InspectionMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


@lru_cache(maxsize=1)
def article_group_load_options() -> tuple[ORMOption, ...]:
    return (load_user(ArticleGroupOrmModel.creator), load_user(ArticleGroupOrmModel.changed_by))


@lru_cache(maxsize=1)
def source_item_type_load_options() -> tuple[ORMOption, ...]:
    return (load_user(SourceItemTypeOrmModel.creator), load_user(SourceItemTypeOrmModel.changed_by))


@lru_cache(maxsize=1)
def fabrication_method_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(FabricationMethodOrmModel.creator),
        load_user(FabricationMethodOrmModel.changed_by),
    )


@lru_cache(maxsize=1)
def inspection_method_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(InspectionMethodOrmModel.creator),
        load_user(InspectionMethodOrmModel.changed_by),
    )


def article_group_orm_to_entity(orm: ArticleGroupOrmModel) -> ArticleGroup:
    return ArticleGroup(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=LocalizedText(values=dict(orm.name or {})),
        label_color=orm.label_color,
        label_font_color=orm.label_font_color,
        description=LocalizedText(values=dict(orm.description or {})),
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def source_item_type_orm_to_entity(orm: SourceItemTypeOrmModel) -> SourceItemType:
    return SourceItemType(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=LocalizedText(values=dict(orm.name or {})),
        label_color=orm.label_color,
        label_font_color=orm.label_font_color,
        description=LocalizedText(values=dict(orm.description or {})),
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
    )


def fabrication_method_orm_to_entity(orm: FabricationMethodOrmModel) -> FabricationMethod:
    return FabricationMethod(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=LocalizedText(values=dict(orm.name or {})),
        label_color=orm.label_color,
        label_font_color=orm.label_font_color,
        description=LocalizedText(values=dict(orm.description or {})),
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        requires_machine=orm.requires_machine,
        required_external=orm.required_external,
        default_supplier_id=orm.default_supplier_id,
        lead_time_days=orm.lead_time_days,
        wait_after_minutes=orm.wait_after_minutes,
        default_for_assemblies=orm.default_for_assemblies,
    )


def inspection_method_orm_to_entity(orm: InspectionMethodOrmModel) -> InspectionMethod:
    return InspectionMethod(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=LocalizedText(values=dict(orm.name or {})),
        label_color=orm.label_color,
        label_font_color=orm.label_font_color,
        description=LocalizedText(values=dict(orm.description or {})),
        sort_order=orm.sort_order,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        default_setup_minutes=orm.default_setup_minutes,
        default_minutes_per_piece=orm.default_minutes_per_piece,
        wait_after_minutes=orm.wait_after_minutes,
        requires_evidence=orm.requires_evidence,
        default_machine_id=orm.default_machine_id,
        default_machine_name=orm.default_machine_name,
    )
