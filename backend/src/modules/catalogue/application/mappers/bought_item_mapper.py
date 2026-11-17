"""
Maps BoughtItem and BoughtItemDemandItem entities to result DTOs.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemPdfFileResult
from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.mappers.product_family_mapper import ProductFamilyMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.platform.application.mappers.user_mapper import UserMapper


class BoughtItemMapper:
    @staticmethod
    def to_result(entity: BoughtItem) -> BoughtItemResult:
        return BoughtItemResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            status=entity.status,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            order_code_1=entity.order_code_1,
            order_code_2=entity.order_code_2,
            gtin=entity.gtin,
            ean=entity.ean,
            tariff_number=entity.tariff_number,
            article_name=entity.article_name,
            article_groups=[ArticleGroupMapper.to_result(g) for g in entity.article_groups],
            data_source=entity.data_source,
            vault_id=entity.vault_id,
            pdm_file_id=entity.pdm_file_id,
            pdm_file_version=entity.pdm_file_version,
            pdm_synced_at=entity.pdm_synced_at,
            pdm_sync_state=entity.pdm_sync_state,
            part_number=entity.part_number,
            revision=entity.revision,
            mass=entity.mass,
            note=entity.note,
            weblink=entity.weblink,
            successor_item_id=entity.successor_item_id,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            manufacturer_id=entity.manufacturer_id,
            manufacturer_name=entity.manufacturer_name,
            product_family_id=entity.product_family_id,
            over_delivery_tolerance_percent=entity.over_delivery_tolerance_percent,
            under_delivery_tolerance_percent=entity.under_delivery_tolerance_percent,
            product_family=(
                ProductFamilyMapper.to_result(entity.product_family)
                if entity.product_family
                else None
            ),
            edp_part_id=entity.edp_part_id,
            edp_synced_at=entity.edp_synced_at,
            pdf_files=[
                BoughtItemPdfFileResult(id=f.id, file_name=f.file_name, mime_type=f.mime_type)
                for f in entity.pdf_files
            ],
            changes=entity.changes,
        )
