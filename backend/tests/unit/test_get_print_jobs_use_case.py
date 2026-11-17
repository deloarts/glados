"""
GetPrintJobs lists the full cross-user print audit trail (who printed
what, from where), so it is gated on read:settings like every other
audit-shaped surface (logs.py,
admin_settings.py's /audit, webhooks.py deliveries).
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.quality.application.use_cases.print_document.get_print_jobs import GetPrintJobs
from src.modules.quality.ports.outbound.repositories.print_job_repository import PrintJobFilterDto


def make_actor(permissions: list[str] | None = None) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=permissions if permissions is not None else [],
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


class FakePrintJobRepository:
    def __init__(self) -> None:
        self.get_multi_calls = 0

    async def get_multi(self, filters: PrintJobFilterDto) -> tuple[int, list]:
        self.get_multi_calls += 1
        return 0, []


async def test_unprivileged_cannot_list_print_jobs() -> None:
    repo = FakePrintJobRepository()
    uc = GetPrintJobs(job_repo=repo)

    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(make_actor(permissions=[]), PrintJobFilterDto())

    assert repo.get_multi_calls == 0


async def test_read_settings_actor_lists_print_jobs() -> None:
    repo = FakePrintJobRepository()
    uc = GetPrintJobs(job_repo=repo)

    result = await uc.execute(
        make_actor(permissions=[Permission.READ_SETTINGS]), PrintJobFilterDto()
    )

    assert result.total == 0
    assert result.items == []
    assert repo.get_multi_calls == 1


async def test_systemuser_can_list_print_jobs() -> None:
    repo = FakePrintJobRepository()
    uc = GetPrintJobs(job_repo=repo)
    actor = make_actor(permissions=[])
    actor.is_systemuser = True

    result = await uc.execute(actor, PrintJobFilterDto())

    assert result.total == 0
    assert repo.get_multi_calls == 1
