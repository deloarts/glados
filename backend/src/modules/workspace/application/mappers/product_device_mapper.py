"""
Converts product devices into result DTOs, composing the two name variants
with the product number on read.
"""

from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceComponentResult
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceResult
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceSignalResult
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.policies.product_device_naming import DeviceName
from src.modules.workspace.domain.policies.product_device_naming import with_product_number


class ProductDeviceMapper:
    @staticmethod
    def component_to_result(entity: ProductDeviceComponent) -> ProductDeviceComponentResult:
        return ProductDeviceComponentResult(
            id=entity.id,
            public_id=entity.public_id,
            role_id=entity.role_id,
            sort_order=entity.sort_order,
            bought_item_id=entity.bought_item_id,
            bought_item_part_number=entity.bought_item_part_number,
            bought_item_article_name=entity.bought_item_article_name,
            eplan_tag=entity.eplan_tag,
            b10d_cycles=entity.b10d_cycles,
            mttfd_years=entity.mttfd_years,
            note=entity.note,
            signals=[
                ProductDeviceSignalResult(
                    signal_type=s.signal_type,
                    meaning=s.meaning,
                    confirms_position_id=s.confirms_position_id,
                    drives_position_id=s.drives_position_id,
                    safety=s.safety,
                    address=s.address,
                    tag_suffix=s.tag_suffix,
                    tag_name=s.tag_name,
                    kind_signal_id=s.kind_signal_id,
                )
                for s in entity.signals
            ],
        )

    @staticmethod
    def to_result(entity: ProductDevice) -> ProductDeviceResult:
        product_number = entity.product_number or ""
        full = with_product_number(product_number, DeviceName(entity.name_utf8, entity.name_ascii))
        return ProductDeviceResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            product_id=entity.product_id,
            product_number=product_number,
            location=entity.location,
            name=entity.name,
            driving_medium_id=entity.driving_medium_id,
            driving_medium_letter=entity.driving_medium_letter,
            number=entity.number,
            name_utf8=entity.name_utf8,
            name_ascii=entity.name_ascii,
            full_name_utf8=full.utf8,
            full_name_ascii=full.ascii,
            kind_id=entity.kind_id,
            description=entity.description,
            initial_position_id=entity.initial_position_id,
            initial_position_value=entity.initial_position_value,
            energy_loss_behaviour_id=entity.energy_loss_behaviour_id,
            energy_restoration_behaviour_id=entity.energy_restoration_behaviour_id,
            monitoring_time_ms=entity.monitoring_time_ms,
            driven_by_id=entity.driven_by_id,
            driven_position_map=entity.driven_position_map,
            safety_relevant=entity.safety_relevant,
            parameters=dict(entity.parameters),
            position_labels=dict(entity.position_labels),
            travel_times_ms=dict(entity.travel_times_ms),
            rendering_file_id=entity.rendering_file_id,
            assembly_file_id=entity.assembly_file_id,
            marker_x=entity.marker_x,
            marker_y=entity.marker_y,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            components=[
                ProductDeviceMapper.component_to_result(c)
                for c in sorted(entity.components, key=lambda c: (c.sort_order, c.id))
            ],
        )
