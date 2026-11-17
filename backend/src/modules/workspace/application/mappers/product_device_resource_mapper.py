"""
Converts the product device resource entities into result DTOs.
"""

from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceKindParameterResult,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceKindPositionResult,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceKindResult,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceKindSignalResult,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    ProductDeviceOptionResult,
)
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption


class ProductDeviceResourceMapper:
    @staticmethod
    def option_to_result(entity: ProductDeviceOption) -> ProductDeviceOptionResult:
        return ProductDeviceOptionResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            category=entity.category,
            label=entity.label.as_dict(),
            letter=entity.letter,
            sort_order=entity.sort_order,
            archived=entity.archived,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )

    @staticmethod
    def kind_to_result(entity: ProductDeviceKind) -> ProductDeviceKindResult:
        return ProductDeviceKindResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            label=entity.label.as_dict(),
            sort_order=entity.sort_order,
            archived=entity.archived,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            without_driving_medium=entity.without_driving_medium,
            positions=[
                ProductDeviceKindPositionResult(
                    id=p.id,
                    public_id=p.public_id,
                    label=p.label.as_dict(),
                    takes_value=p.takes_value,
                    unit=p.unit,
                    sort_order=p.sort_order,
                    archived=p.archived,
                    plc_state_name=p.plc_state_name,
                    plc_command_name=p.plc_command_name,
                )
                for p in sorted(entity.positions, key=lambda p: (p.archived, p.sort_order, p.id))
            ],
            parameters=[
                ProductDeviceKindParameterResult(
                    id=p.id,
                    public_id=p.public_id,
                    label=p.label.as_dict(),
                    unit=p.unit,
                    value_type=p.value_type,
                    sort_order=p.sort_order,
                    archived=p.archived,
                )
                for p in sorted(entity.parameters, key=lambda p: (p.archived, p.sort_order, p.id))
            ],
            signals=[
                ProductDeviceKindSignalResult(
                    id=s.id,
                    public_id=s.public_id,
                    label=s.label.as_dict(),
                    signal_type=s.signal_type,
                    plc_name=s.plc_name,
                    sort_order=s.sort_order,
                    archived=s.archived,
                )
                for s in sorted(entity.signals, key=lambda s: (s.archived, s.sort_order, s.id))
            ],
        )
