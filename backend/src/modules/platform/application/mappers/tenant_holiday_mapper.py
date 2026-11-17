"""Converts TenantHoliday domain entities to result DTOs."""

from src.modules.platform.application.dto.tenant_holiday_dto import TenantHolidayResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday


class TenantHolidayMapper:
    @staticmethod
    def to_result(entity: TenantHoliday) -> TenantHolidayResult:
        return TenantHolidayResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            name=entity.name,
            category=entity.category,
            start_date=entity.start_date,
            end_date=entity.end_date,
            creator_id=entity.creator_id,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
