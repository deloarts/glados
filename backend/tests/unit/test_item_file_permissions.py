"""
Item-file upload/rename/delete (bought item, made item, order, source
item, product) requires the parent aggregate's write permission, not just
an active session. Each use case checks the permission before touching
storage, so these tests
construct the use cases with placeholder collaborators and assert an
unprivileged actor is rejected up front.

Product files are the one exception to "the check is the first action":
ProductRules scopes update rights to the product (manage:projects OR being
its designated user), so the product must be loaded first. Those tests pass
a real fake product repository instead of a placeholder, and still use
placeholders for everything else to prove nothing further is touched.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.bought_item_file_dto import UpdateBoughtItemFileCommand
from src.modules.catalogue.application.dto.made_item_file_dto import UpdateMadeItemFileCommand
from src.modules.catalogue.application.dto.source_item_file_dto import UpdateSourceItemFileCommand
from src.modules.catalogue.application.use_cases.bought_item.delete_bought_item_file import (
    DeleteBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item_file import (
    UpdateBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.upload_bought_item_file import (
    UploadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.delete_made_item_file import (
    DeleteMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.update_made_item_file import (
    UpdateMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.delete_source_item_file import (
    DeleteSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item_file import (
    UpdateSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.upload_source_item_file import (
    UploadSourceItemFile,
)
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.fulfillment.application.dto.production_order_file_dto import (
    UpdateProductionOrderFileCommand,
)
from src.modules.fulfillment.application.use_cases.order.delete_order_file import DeleteOrderFile
from src.modules.fulfillment.application.use_cases.order.upload_order_file import UploadOrderFile
from src.modules.fulfillment.application.use_cases.production_order.delete_production_order_file import (
    DeleteProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.download_production_order_file import (
    DownloadProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.get_production_order_files import (
    GetProductionOrderFiles,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order_file import (
    UpdateProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.upload_production_order_file import (
    UploadProductionOrderFile,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.workspace.application.dto.product_file_dto import UpdateProductFileCommand
from src.modules.workspace.application.use_cases.product.delete_product_file import (
    DeleteProductFile,
)
from src.modules.workspace.application.use_cases.product.update_product_file import (
    UpdateProductFile,
)
from src.modules.workspace.application.use_cases.product.upload_product_file import (
    UploadProductFile,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from tests.unit.fakes import FakeUnitOfWork


def _user(permissions: list[str]) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
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


class _Boom:
    """Any attribute access explodes, proves the permission check happens
    before any collaborator is touched."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"collaborator was used before the permission check ({name})")


NO_PERMS = _user([])


async def test_upload_bought_item_file_requires_write() -> None:
    uc = UploadBoughtItemFile(
        item_repo=_Boom(), file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS,
            item_id=1,
            data=b"x",
            file_name="f.pdf",
            content_type="application/pdf",
            category=BoughtItemFileCategory.PDF,
        )


async def test_update_bought_item_file_requires_write() -> None:
    uc = UpdateBoughtItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS, file_id=1, command=UpdateBoughtItemFileCommand(file_name="n")
        )


async def test_delete_bought_item_file_requires_write() -> None:
    uc = DeleteBoughtItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1)


async def test_upload_made_item_file_requires_write() -> None:
    uc = UploadMadeItemFile(
        item_repo=_Boom(), file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS,
            item_id=1,
            data=b"x",
            file_name="f.pdf",
            content_type="application/pdf",
            category=MadeItemFileCategory.PDF,
        )


async def test_update_made_item_file_requires_write() -> None:
    uc = UpdateMadeItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS, file_id=1, command=UpdateMadeItemFileCommand(file_name="n")
        )


async def test_delete_made_item_file_requires_write() -> None:
    uc = DeleteMadeItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1)


async def test_upload_order_file_requires_write() -> None:
    uc = UploadOrderFile(
        order_repo=_Boom(), file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS,
            order_id=1,
            data=b"x",
            file_name="f.pdf",
            content_type="application/pdf",
            category=OrderFileCategory.GENERAL,
        )


async def test_delete_order_file_requires_write() -> None:
    uc = DeleteOrderFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1)


async def test_a_permitted_actor_passes_the_gate() -> None:
    """With the write permission, the gate lets execution proceed, proven by
    reaching the placeholder collaborator (which raises AssertionError, not
    InsufficientPermissionsError)."""
    actor = _user([Permission.WRITE_BOUGHT_ITEMS])
    uc = DeleteBoughtItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(AssertionError):
        await uc.execute(actor=actor, file_id=1)


# ── Source item files ─────────────────────────────────────────────────


async def test_upload_source_item_file_requires_write() -> None:
    uc = UploadSourceItemFile(
        item_repo=_Boom(), file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS,
            item_id=1,
            data=b"x",
            file_name="cert.pdf",
            content_type="application/pdf",
            category=SourceItemFileCategory.PDF,
        )


async def test_update_source_item_file_requires_write() -> None:
    uc = UpdateSourceItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS, file_id=1, command=UpdateSourceItemFileCommand(file_name="n")
        )


async def test_delete_source_item_file_requires_write() -> None:
    uc = DeleteSourceItemFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1)


# ── Product files ─────────────────────────────────────────────────────


def _product(designated_user_id: int = 99) -> Product:
    return Product(
        id=1,
        created=datetime.now(UTC),
        product_number="P-001",
        designated_user_id=designated_user_id,
    )


class _FakeProductRepo:
    """The one collaborator the product file use cases legitimately touch
    before checking permission, because the rule needs the product."""

    def __init__(self, product: Product | None) -> None:
        self._product = product

    async def get_by_id(self, id: int) -> Product | None:
        return self._product


class _FakeProductFileRepo:
    def __init__(self, product_id: int = 1) -> None:
        self._product_id = product_id

    async def get_by_id(self, id: int) -> object:
        return type("_File", (), {"product_id": self._product_id, "storage_path": "p"})()


async def test_upload_product_file_requires_manage_or_ownership() -> None:
    uc = UploadProductFile(
        product_repo=_FakeProductRepo(_product()),
        file_repo=_Boom(),
        storage=_Boom(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS,
            product_id=1,
            data=b"x",
            file_name="spec.pdf",
            content_type="application/pdf",
            category=ProductFileCategory.PDF,
        )


async def test_update_product_file_requires_manage_or_ownership() -> None:
    uc = UpdateProductFile(
        product_repo=_FakeProductRepo(_product()),
        file_repo=_FakeProductFileRepo(),
        storage=_Boom(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1, command=UpdateProductFileCommand(file_name="n"))


async def test_delete_product_file_requires_manage_or_ownership() -> None:
    uc = DeleteProductFile(
        product_repo=_FakeProductRepo(_product()),
        file_repo=_FakeProductFileRepo(),
        storage=_Boom(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1)


async def test_a_products_designated_user_passes_the_gate() -> None:
    """The ownership branch of ProductRules: an actor with no permissions at
    all may attach files to a product they are designated on. Proven by
    reaching the placeholder collaborator (AssertionError, not
    InsufficientPermissionsError)."""
    uc = UploadProductFile(
        product_repo=_FakeProductRepo(_product(designated_user_id=NO_PERMS.id)),
        file_repo=_Boom(),
        storage=_Boom(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(AssertionError):
        await uc.execute(
            actor=NO_PERMS,
            product_id=1,
            data=b"x",
            file_name="spec.pdf",
            content_type="application/pdf",
            category=ProductFileCategory.PDF,
        )


# ── Production order files (QA/inspection evidence) ────────────────────


async def test_list_production_order_files_requires_write_inspections() -> None:
    uc = GetProductionOrderFiles(order_repo=_Boom(), file_repo=_Boom(), storage=_Boom())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, order_id=1)


async def test_upload_production_order_file_requires_write_inspections() -> None:
    uc = UploadProductionOrderFile(
        order_repo=_Boom(), file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS,
            order_id=1,
            data=b"x",
            file_name="report.pdf",
            content_type="application/pdf",
            category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
        )


async def test_update_production_order_file_requires_write_inspections() -> None:
    uc = UpdateProductionOrderFile(file_repo=_Boom(), storage=_Boom(), uow=FakeUnitOfWork())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(
            actor=NO_PERMS, file_id=1, command=UpdateProductionOrderFileCommand(file_name="n")
        )


async def test_delete_production_order_file_requires_write_inspections() -> None:
    uc = DeleteProductionOrderFile(
        file_repo=_Boom(), storage=_Boom(), order_repo=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, file_id=1)


async def test_write_inspections_actor_passes_the_gate() -> None:
    """With write:inspections, the gate lets execution proceed, proven by
    reaching the placeholder collaborator (AssertionError, not
    InsufficientPermissionsError)."""
    actor = _user([Permission.WRITE_INSPECTIONS])
    uc = DeleteProductionOrderFile(
        file_repo=_Boom(), storage=_Boom(), order_repo=_Boom(), uow=FakeUnitOfWork()
    )
    with pytest.raises(AssertionError):
        await uc.execute(actor=actor, file_id=1)


async def test_download_production_order_file_requires_write_inspections() -> None:
    uc = DownloadProductionOrderFile(file_repo=_Boom(), storage=_Boom())
    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=NO_PERMS, order_id=1, file_id=1)


async def test_write_inspections_actor_can_download() -> None:
    class _FakeProductionOrderFileRepo:
        async def get_by_id(self, id: int) -> ProductionOrderFile | None:
            return ProductionOrderFile(
                id=1,
                production_order_id=1,
                file_name="report.pdf",
                stored_name="stored.pdf",
                mime_type="application/pdf",
                size_bytes=3,
                storage_path="production_orders/1/report/stored.pdf",
                sha256="x",
                category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
                created=datetime.now(UTC),
                uploaded_by_user_id=1,
            )

    class _FakeStorage:
        async def download(self, key: str) -> tuple[bytes, str]:
            return b"pdf-bytes", "application/pdf"

    actor = _user([Permission.WRITE_INSPECTIONS])
    uc = DownloadProductionOrderFile(
        file_repo=_FakeProductionOrderFileRepo(), storage=_FakeStorage()
    )
    file, data, content_type = await uc.execute(actor=actor, order_id=1, file_id=1)
    assert data == b"pdf-bytes"
    assert content_type == "application/pdf"
    assert file.id == 1


async def test_upload_product_file_for_an_unknown_product_is_not_found() -> None:
    """Documents the deliberate ordering deviation: the product is resolved
    before the permission check, so a missing product surfaces as a 404
    rather than a permission error."""
    uc = UploadProductFile(
        product_repo=_FakeProductRepo(None),
        file_repo=_Boom(),
        storage=_Boom(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(ProductNotFoundError):
        await uc.execute(
            actor=NO_PERMS,
            product_id=999,
            data=b"x",
            file_name="spec.pdf",
            content_type="application/pdf",
            category=ProductFileCategory.PDF,
        )
