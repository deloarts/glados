"""The second set of infoscreen widgets with real rows: the machine detail
widget with its drawing link served without a credential, the active
products and projects, overdue deliveries, the weather through a stand-in
service, and the place search of the location picker."""

import itertools
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap import bindings
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_file_repository import (
    SqlAlchemyMadeItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.operations.adapters.inbound.api.deps import terminals as terminal_deps
from src.modules.operations.domain.errors import WeatherUnavailableError
from src.modules.operations.ports.outbound.weather_port import WeatherClientContact
from src.modules.operations.ports.outbound.weather_port import WeatherDay
from src.modules.operations.ports.outbound.weather_port import WeatherForecast
from src.modules.operations.ports.outbound.weather_port import WeatherNow
from src.modules.operations.ports.outbound.weather_port import WeatherPlace
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from tests.integration import _lifecycle_seed as seed
from tests.integration._tenant_day import tenant_today
from tests.integration._terminal_helpers import INFOSCREENS
from tests.integration._terminal_helpers import device_client
from tests.integration._terminal_helpers import seed_production
from tests.integration._terminal_helpers import seed_security

pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")

_PDF = b"%PDF-1.4 drawing"
_screen_numbers = itertools.count(1)


@pytest.fixture(autouse=True)
async def _settings(db: AsyncSession) -> None:
    await seed_security(db)
    await seed_production(db)


@pytest.fixture
async def storage(db: AsyncSession, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from src.modules.platform.infrastructure.config.settings import cfg

    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(media))
    await db.execute(text("DELETE FROM admin_storage_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_storage(
        AdminStorageSettings(
            id=1,
            provider="local",
            enabled=True,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key=None,
            region=None,
            use_ssl=False,
            backup_enabled=False,
            backup_path="backups",
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    return media


@pytest.fixture
async def writer(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[Permission.WRITE_INFOSCREENS, Permission.WRITE_MACHINES],
        username="writer",
        email="writer@example.com",
    )


async def _screen(writer: httpx.AsyncClient, *widgets: dict[str, Any]) -> list[dict[str, Any]]:
    """The widget data of a screen with one page holding `widgets`."""
    layout = {1: "full", 2: "two_columns", 4: "grid_2x2"}[len(widgets)]
    created = await writer.post(
        INFOSCREENS,
        json={
            "name": f"Second set {next(_screen_numbers)}",
            "pages": [{"layout": layout, "slots": list(widgets)}],
        },
    )
    assert created.status_code == 201, created.text
    feed = await writer.get(f"{INFOSCREENS}/{created.json()['id']}/feed")
    assert feed.status_code == 200, feed.text
    widgets_of_page: list[dict[str, Any]] = feed.json()["widgets"][0]
    return widgets_of_page


async def _source_item(db: AsyncSession) -> SourceItem:
    item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=1,
            dimension="Ø40",
            material="1.0503",
            mass=None,
            note=None,
            order_code_1=None,
            order_code_2=None,
            status=SourceItemCatalogueStatus.ACTIVE,
            creator_id=1,
            approver_id=None,
            manufacturer_id=None,
            successor_item_id=None,
        )
    )
    await db.commit()
    return item


async def _made_item(db: AsyncSession, source_item_id: int | None) -> MadeItem:
    item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="B",
            revision_date=None,
            revision_note=None,
            article_name="Shaft",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number="MD-100",
            material="1.0503",
            mass=850,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=source_item_id,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return item


async def _drawing(db: AsyncSession, storage: Any, item_id: int) -> MadeItemFile:
    key = f"made-{item_id}/drawing.pdf"
    (storage / f"made-{item_id}").mkdir()
    (storage / key).write_bytes(_PDF)
    saved = await SqlAlchemyMadeItemFileRepository(db).save(
        MadeItemFile(
            id=0,
            made_item_id=item_id,
            file_name="MD-100.pdf",
            stored_name="drawing.pdf",
            mime_type="application/pdf",
            size_bytes=len(_PDF),
            storage_path=key,
            sha256="x",
            category=MadeItemFileCategory.DRAWING,
            created=datetime.now(UTC),
            uploaded_by_user_id=1,
        )
    )
    await db.commit()
    return saved


async def _lot(db: AsyncSession, status: str, item_id: int, project_id: int = 1) -> Any:
    """A lot of the given made item and project; the seed helper fixes both."""
    lot = await seed.lot(db, status)
    lot.made_item_id = item_id
    lot.project_id = project_id
    await db.flush()
    return lot


async def _project(db: AsyncSession, number: str, **values: Any) -> Project:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number=number, **values)
    )
    await db.commit()
    return project


async def test_machine_detail_shows_the_running_order_with_its_drawing_and_raw_material(
    db: AsyncSession, storage: Any, writer: httpx.AsyncClient
) -> None:
    machine = await writer.post(
        "/api/v1/web/production-machines/",
        json={"internal_name": "Lathe", "vendor": "DMG", "model": "CTX"},
    )
    machine_id = machine.json()["id"]
    source = await _source_item(db)
    item = await _made_item(db, source.id)
    await _drawing(db, storage, item.id)
    project = await _project(db, "P-MD-1")
    lot = await _lot(db, "in_progress", item.id, project.id)
    position = await seed.position(db, lot, "internal", "ordered_or_queued")
    await seed.production_order(
        db, position, "in_progress", machine_id=machine_id, queue_sequence=1, quantity_completed=4
    )
    await seed.production_order(db, position, "queued", machine_id=machine_id, queue_sequence=2)
    await db.commit()

    [detail] = await _screen(writer, {"type": "machine_detail", "machine_id": machine_id})

    assert detail["machine_name"] == "Lathe"
    assert detail["state"] == "running"
    order = detail["order"]
    assert order["current"] is True
    assert (order["lot_number"], order["part_number"], order["item_name"]) == (
        lot.lot_number,
        "MD-100",
        "Shaft",
    )
    assert (order["revision"], order["material"], order["mass_grams"]) == ("B", "1.0503", 850)
    assert order["quantity_completed"] == 4
    assert order["lot"]["lot_number"] == lot.lot_number
    assert order["lot"]["project_number"] == "P-MD-1"
    assert order["lot"]["customer_name"] is None
    raw = order["raw_material"]
    assert (raw["kind"], raw["material"], raw["dimension"]) == ("source", "1.0503", "Ø40")
    assert not any("planned" in key for key in order)
    [following] = detail["next"]
    assert following["lot_number"] == lot.lot_number
    assert "planned_start" not in following and "planned_end" not in following

    url = order["drawing_url"]
    assert url.startswith("/api/v1/web/terminal-device/drawings/")
    async with device_client() as anonymous:
        served = await anonymous.get(url)
        assert served.status_code == 200, served.text
        assert served.content == _PDF
        assert served.headers["content-type"] == "application/pdf"
        assert served.headers["cache-control"].startswith("private, max-age=")
        assert (await anonymous.get(url + "x")).status_code == 404

        item.archived = True
        await SqlAlchemyMadeItemRepository(db).save(item)
        await db.commit()
        archived = await anonymous.get(url)
        assert archived.status_code == 404
        assert archived.json()["code"] == "InfoscreenDrawingNotFoundError"


async def test_machine_detail_shows_the_next_order_without_a_drawing_when_asked(
    db: AsyncSession, storage: Any, writer: httpx.AsyncClient
) -> None:
    machine = await writer.post(
        "/api/v1/web/production-machines/",
        json={"internal_name": "Mill", "vendor": "DMG", "model": "DMU"},
    )
    machine_id = machine.json()["id"]
    item = await _made_item(db, None)
    await _drawing(db, storage, item.id)
    lot = await _lot(db, "planned", item.id)
    position = await seed.position(db, lot, "internal", "ordered_or_queued")
    await seed.production_order(db, position, "queued", machine_id=machine_id, queue_sequence=1)
    await db.commit()

    detail, unknown = await _screen(
        writer,
        {"type": "machine_detail", "machine_id": machine_id, "show_drawing": False},
        {"type": "machine_detail", "machine_id": 999_999},
    )
    assert detail["order"]["current"] is False
    assert detail["order"]["drawing_url"] is None
    assert detail["order"]["raw_material"] is None
    assert detail["next"] == []
    assert unknown["machine_name"] is None and unknown["order"] is None


async def test_products_and_projects_show_only_the_active_ones(
    db: AsyncSession, writer: httpx.AsyncClient
) -> None:
    products = SqlAlchemyProductRepository(db)
    active = await products.save(
        Product(
            id=0,
            created=datetime.now(UTC),
            product_number="M-200",
            designation="Press line",
            creator_id=1,
        )
    )
    await products.save(
        Product(
            id=0, created=datetime.now(UTC), product_number="M-100", is_active=False, creator_id=1
        )
    )
    await db.commit()
    await _project(db, "P-2", description="Retrofit", product_id=active.id)
    await _project(db, "P-1", description="New line")
    await _project(db, "P-3", status=ProjectStatus.ON_HOLD, product_id=active.id)

    with_projects, plain, projects, _ = await _screen(
        writer,
        {"type": "products", "show_projects": True},
        {"type": "products"},
        {"type": "projects"},
        {"type": "projects", "show_customer": True},
    )

    assert [p["product_number"] for p in with_projects["products"]] == ["M-200"]
    [row] = with_projects["products"]
    assert row["designation"] == "Press line"
    assert [p["project_number"] for p in row["projects"]] == ["P-2"]
    assert plain["products"][0]["projects"] == []

    numbers = [p["project_number"] for p in projects["projects"]]
    assert "P-3" not in numbers
    assert numbers.index("P-1") < numbers.index("P-2")
    retrofit = next(p for p in projects["projects"] if p["project_number"] == "P-2")
    assert retrofit["product_number"] == "M-200"
    assert retrofit["product_designation"] == "Press line"


async def test_deliveries_put_overdue_lines_first_only_when_asked(
    db: AsyncSession, writer: httpx.AsyncClient
) -> None:
    today = tenant_today()
    late = await seed.order(db, "ordered", expected_delivery_date=today - timedelta(days=2))
    await seed.line(db, late, "ordered", expected_delivery_date=today - timedelta(days=2))
    due = await seed.order(db, "ordered", expected_delivery_date=today)
    await seed.line(db, due, "ordered", expected_delivery_date=today)
    await db.commit()

    plain, overdue = await _screen(
        writer,
        {"type": "deliveries_expected"},
        {"type": "deliveries_expected", "show_overdue": True},
    )
    assert [r["days_late"] for r in plain["deliveries"]] == [None]
    assert [r["days_late"] for r in overdue["deliveries"]] == [2, None]


class _Weather:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.asked: list[tuple[float, float, int]] = []
        self.timezones: list[str] = []

    async def forecast(
        self,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
        contact: WeatherClientContact,
    ) -> WeatherForecast:
        self.asked.append((latitude, longitude, days))
        self.timezones.append(timezone)
        if self.fail:
            raise WeatherUnavailableError("down")
        today = tenant_today()
        return WeatherForecast(
            now=WeatherNow(temperature=3.5, symbol="lightrain", wind_speed=9.0, is_day=True),
            days=[
                WeatherDay(
                    day=today + timedelta(days=i),
                    symbol="rain",
                    temperature_max=6.0,
                    temperature_min=1.0,
                    precipitation_mm=2.5,
                )
                for i in range(days + 1)
            ],
            fetched_at=datetime.now(UTC),
            attribution="MET Norway",
        )

    async def search_places(
        self, query: str, country_code: str, language: str, contact: WeatherClientContact
    ) -> list[WeatherPlace]:
        return [
            WeatherPlace(
                name=query,
                region="Salzburg",
                country_code=country_code.upper(),
                latitude=47.32,
                longitude=12.8,
            )
        ]


_WEATHER = {
    "type": "weather",
    "location_name": "Zell am See",
    "country_code": "AT",
    "latitude": 47.3233,
    "longitude": 12.7956,
    "days": 2,
}


async def test_weather_comes_from_the_service_unless_switched_off(
    db: AsyncSession, writer: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _Weather()
    monkeypatch.setattr(bindings, "get_weather_service", lambda: service)

    [weather] = await _screen(writer, _WEATHER)
    assert weather["status"] == "ok"
    assert weather["location_name"] == "Zell am See"
    assert weather["now"]["temperature"] == 3.5
    assert len(weather["days"]) == 3
    assert weather["days"][0]["precipitation_mm"] == 2.5
    assert weather["attribution"] == "MET Norway"
    assert service.asked == [(47.32, 12.8, 2)]
    assert service.timezones and service.timezones[0]

    service.fail = True
    [down] = await _screen(writer, _WEATHER)
    assert down["status"] == "unavailable" and down["now"] is None

    await seed_security(db, enable_infoscreen_weather=False)
    service.asked.clear()
    [off] = await _screen(writer, _WEATHER)
    assert off["status"] == "off"
    assert service.asked == []


async def test_place_search_needs_write_infoscreens_and_the_weather_on(
    db: AsyncSession,
    writer: httpx.AsyncClient,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(terminal_deps, "get_weather_service", lambda: _Weather())
    url = f"{INFOSCREENS}/weather-places"

    found = await writer.get(url, params={"q": "Zell am See", "country": "at", "language": "deAT"})
    assert found.status_code == 200, found.text
    assert found.json() == [
        {
            "name": "Zell am See",
            "region": "Salzburg",
            "country_code": "AT",
            "latitude": 47.32,
            "longitude": 12.8,
        }
    ]
    assert (await writer.get(url, params={"q": "L", "country": "AT"})).status_code == 422

    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    assert (await reader.get(url, params={"q": "Zell am See", "country": "AT"})).status_code == 403

    await seed_security(db, enable_infoscreen_weather=False)
    switched_off = await writer.get(url, params={"q": "Zell am See", "country": "AT"})
    assert switched_off.status_code == 503
    assert switched_off.json()["code"] == "WeatherUnavailableError"
