"""
The username and status code filters of SqlAlchemyLogRepository.get_multi,
which back the admin Logs tab's column filters.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.log_repository import (
    SqlAlchemyLogRepository,
)
from src.modules.platform.ports.outbound.repositories.log_repository import LogFilterDto

_NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


async def _seed(db: AsyncSession) -> None:
    for username, status_code in (
        ("Zoe-Filter", 200),
        ("zoe-filter-2", 404),
        ("max-filter", 404),
    ):
        db.add(
            LogOrmModel(
                timestamp=_NOW,
                level="INFO",
                username=username,
                status_code=status_code,
                path="/api/v1/web/filter-probe",
            )
        )
    await db.commit()


async def test_username_filter_matches_part_of_the_name_ignoring_case(db: AsyncSession) -> None:
    await _seed(db)

    total, entries = await SqlAlchemyLogRepository(db).get_multi(
        LogFilterDto(username_contains="ZOE-filter", path_contains="filter-probe")
    )

    assert total == 2
    assert sorted(e.username or "" for e in entries) == ["Zoe-Filter", "zoe-filter-2"]


async def test_status_code_filter_matches_exactly(db: AsyncSession) -> None:
    await _seed(db)

    total, entries = await SqlAlchemyLogRepository(db).get_multi(
        LogFilterDto(status_code=404, path_contains="filter-probe")
    )

    assert total == 2
    assert sorted(e.username or "" for e in entries) == ["max-filter", "zoe-filter-2"]
