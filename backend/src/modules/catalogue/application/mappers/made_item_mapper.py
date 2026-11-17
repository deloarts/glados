"""Converts between MadeItem/MadeItemProcess domain entities and DTOs, including related
items and fabrication data."""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemProcessResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.platform.application.mappers.user_mapper import UserMapper


class MadeItemMapper:
    @staticmethod
    def to_result(entity: MadeItem) -> MadeItemResult:
        return MadeItemResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            status=entity.status,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            revision=entity.revision,
            revision_date=entity.revision_date,
            revision_note=entity.revision_note,
            article_name=entity.article_name,
            article_groups=[ArticleGroupMapper.to_result(g) for g in entity.article_groups],
            data_source=entity.data_source,
            vault_id=entity.vault_id,
            pdm_file_id=entity.pdm_file_id,
            pdm_file_version=entity.pdm_file_version,
            pdm_synced_at=entity.pdm_synced_at,
            pdm_sync_state=entity.pdm_sync_state,
            part_number=entity.part_number,
            material=entity.material,
            mass=entity.mass,
            base_size=entity.base_size,
            note=entity.note,
            weblink=entity.weblink,
            successor_item_id=entity.successor_item_id,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            bought_item_id=entity.bought_item_id,
            bought_item=BoughtItemMapper.to_result(entity.bought_item)
            if entity.bought_item
            else None,
            source_item_id=entity.source_item_id,
            pdm_source_item_id=entity.pdm_source_item_id,
            source_item=SourceItemMapper.to_result(entity.source_item)
            if entity.source_item
            else None,
            customer_id=entity.customer_id,
            customer_name=entity.customer_name,
            customer_part_number=entity.customer_part_number,
            customer_revision=entity.customer_revision,
            source_label=entity.source_label,
            source_sublabel=entity.source_sublabel,
            processes=[MadeItemProcessMapper.to_result(p) for p in entity.processes],
            changes=entity.changes,
        )


class MadeItemProcessMapper:
    @staticmethod
    def to_result(entity: MadeItemProcess) -> MadeItemProcessResult:
        return MadeItemProcessResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            note=entity.note,
            estimated_setup_minutes=entity.estimated_setup_minutes,
            estimated_minutes_per_piece=entity.estimated_minutes_per_piece,
            creator_id=entity.creator_id,
            role=entity.role,
            inspection_method_id=entity.inspection_method_id,
            fabrication_method_id=entity.fabrication_method_id,
            fabrication_method_name=entity.fabrication_method_name.as_dict(),
            inspection_method_name=(
                entity.inspection_method_name.as_dict() if entity.inspection_method_name else None
            ),
            made_item_id=entity.made_item_id,
            position=entity.position,
            group_index=entity.group_index,
        )
