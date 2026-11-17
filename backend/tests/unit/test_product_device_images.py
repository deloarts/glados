from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from typing import cast
from uuid import UUID

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
from src.modules.workspace.application.use_cases.product_device.images import (
    RemoveProductDeviceImage,
)
from src.modules.workspace.application.use_cases.product_device.images import SetProductDeviceImage
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.value_objects.product_device_image_slot import (
    ProductDeviceImageSlot,
)
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 10, 23, tzinfo=UTC)
DEVICE_UUID = UUID("11111111-2222-3333-4444-555555555555")


def _user(permissions: list[str]) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=NOW,
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=permissions,
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


def _device(**overrides: Any) -> ProductDevice:
    values: dict[str, Any] = {
        "id": 5,
        "public_id": DEVICE_UUID,
        "created": NOW,
        "changed": NOW,
        "changes": [],
        "product_id": 3,
        "location": "B01",
        "name": "Hubzylinder",
        "driving_medium_id": 1,
        "number": 1,
        "name_utf8": "B01 Hubzylinder P1",
        "name_ascii": "B01_Hubzylinder_P1",
        "name_ascii_key": "b01_hubzylinder_p1",
        "group_key": "b01_hubzylinder_p",
        "kind_id": 1,
        "creator_id": 1,
        "product_number": "M26001",
        "driving_medium_letter": "P",
    }
    values.update(overrides)
    return ProductDevice(**values)


class _Devices:
    def __init__(self, device: ProductDevice) -> None:
        self.device = device

    async def get_by_id(self, id: int) -> ProductDevice | None:
        return self.device

    async def save(self, device: ProductDevice) -> ProductDevice:
        self.device = device
        return device


class _Products:
    async def get_by_id(self, id: int) -> Any:
        return SimpleNamespace(
            id=id, designated_user_id=99, product_number="M26001", archived=False
        )


class _Upload:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ProductFileCategory]] = []

    async def execute(
        self,
        actor: User,
        product_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: ProductFileCategory,
    ) -> Any:
        self.calls.append((file_name, category))
        return SimpleNamespace(id=70 + len(self.calls))


class _Delete:
    def __init__(self) -> None:
        self.deleted: list[int] = []

    async def execute(self, actor: User, file_id: int) -> None:
        self.deleted.append(file_id)


def _set(
    device: ProductDevice, uow: FakeUnitOfWork
) -> tuple[SetProductDeviceImage, _Devices, _Upload, _Delete]:
    devices, upload, delete = _Devices(device), _Upload(), _Delete()
    use_case = SetProductDeviceImage(
        device_repo=cast(Any, devices),
        product_repo=cast(Any, _Products()),
        upload_file=cast(Any, upload),
        delete_file=cast(Any, delete),
        uow=uow,
    )
    return use_case, devices, upload, delete


async def test_product_device_images_upload_replaces_and_deletes_the_old_file(
    fake_uow: FakeUnitOfWork,
) -> None:
    use_case, devices, upload, delete = _set(_device(rendering_file_id=40), fake_uow)

    result = await use_case.execute(
        _user([Permission.MANAGE_PROJECTS]), 5, ProductDeviceImageSlot.RENDERING, b"x", "image/png"
    )

    assert upload.calls == [(f"{DEVICE_UUID}.png", ProductFileCategory.DEVICE_RENDERING)]
    assert result.rendering_file_id == 71
    assert devices.device.rendering_file_id == 71
    assert delete.deleted == [40]


async def test_product_device_images_assembly_slot_is_its_own_file(
    fake_uow: FakeUnitOfWork,
) -> None:
    use_case, devices, upload, delete = _set(_device(rendering_file_id=40), fake_uow)

    await use_case.execute(
        _user([Permission.MANAGE_PROJECTS]), 5, ProductDeviceImageSlot.ASSEMBLY, b"x", "image/png"
    )

    assert upload.calls == [(f"{DEVICE_UUID}-assembly.png", ProductFileCategory.DEVICE_ASSEMBLY)]
    assert devices.device.assembly_file_id == 71
    assert devices.device.rendering_file_id == 40
    assert delete.deleted == []


async def test_product_device_images_remove_clears_the_slot_and_deletes_the_file(
    fake_uow: FakeUnitOfWork,
) -> None:
    devices, delete = _Devices(_device(assembly_file_id=41)), _Delete()
    use_case = RemoveProductDeviceImage(
        device_repo=cast(Any, devices),
        product_repo=cast(Any, _Products()),
        delete_file=cast(Any, delete),
        uow=fake_uow,
    )

    result = await use_case.execute(
        _user([Permission.MANAGE_PROJECTS]), 5, ProductDeviceImageSlot.ASSEMBLY
    )

    assert result.assembly_file_id is None
    assert delete.deleted == [41]


async def test_product_device_images_need_the_product_rights(fake_uow: FakeUnitOfWork) -> None:
    use_case, _, upload, _ = _set(_device(), fake_uow)
    with pytest.raises(InsufficientPermissionsError):
        await use_case.execute(
            _user([Permission.WRITE_PROJECTS]),
            5,
            ProductDeviceImageSlot.RENDERING,
            b"x",
            "image/png",
        )
    assert upload.calls == []
