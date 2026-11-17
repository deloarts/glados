"""Use case factories: product devices, the hand-maintained lists they pick
from, and the impact of renumbering a product.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.bindings import get_product_documents
from src.modules.workspace.adapters.inbound.api.deps.product_files import (
    get_delete_product_file_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_files import (
    get_upload_product_file_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_plc_environment_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_product_device_check_repo,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_product_device_kind_repo,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_product_device_option_repo,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_device_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.api import IProductDocuments
from src.modules.workspace.application.use_cases.product.delete_product_file import (
    DeleteProductFile,
)
from src.modules.workspace.application.use_cases.product.get_renumber_impact import (
    GetProductRenumberImpact,
)
from src.modules.workspace.application.use_cases.product.upload_product_file import (
    UploadProductFile,
)
from src.modules.workspace.application.use_cases.product_device.assembler import (
    ProductDeviceAssembler,
)
from src.modules.workspace.application.use_cases.product_device.completeness import (
    GetProductDeviceCompleteness,
)
from src.modules.workspace.application.use_cases.product_device.completeness import (
    SetProductDeviceCheck,
)
from src.modules.workspace.application.use_cases.product_device.devices import CreateProductDevice
from src.modules.workspace.application.use_cases.product_device.devices import GetProductDevice
from src.modules.workspace.application.use_cases.product_device.devices import GetProductDevices
from src.modules.workspace.application.use_cases.product_device.devices import (
    PreviewProductDeviceName,
)
from src.modules.workspace.application.use_cases.product_device.devices import (
    SetProductDeviceArchived,
)
from src.modules.workspace.application.use_cases.product_device.devices import UpdateProductDevice
from src.modules.workspace.application.use_cases.product_device.images import (
    RemoveProductDeviceImage,
)
from src.modules.workspace.application.use_cases.product_device.images import SetProductDeviceImage
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    CreateProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    GetProductDeviceKinds,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    MoveProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    PlaceProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    SetProductDeviceKindArchived,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    UpdateProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    CreateProductDeviceOption,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    GetProductDeviceOptions,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    MoveProductDeviceOption,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    PlaceProductDeviceOption,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    SetProductDeviceOptionArchived,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    UpdateProductDeviceOption,
)
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_check_repository import (
    IProductDeviceCheckRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceOptionRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository

# ── Resources ─────────────────────────────────────────────────────────


def get_product_device_options_use_case(
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
) -> GetProductDeviceOptions:
    return GetProductDeviceOptions(option_repo=option_repo)


def get_create_product_device_option_use_case(
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateProductDeviceOption:
    return CreateProductDeviceOption(option_repo=option_repo, settings_repo=settings_repo, uow=uow)


def get_update_product_device_option_use_case(
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateProductDeviceOption:
    return UpdateProductDeviceOption(
        option_repo=option_repo, device_repo=device_repo, settings_repo=settings_repo, uow=uow
    )


def get_set_product_device_option_archived_use_case(
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetProductDeviceOptionArchived:
    return SetProductDeviceOptionArchived(option_repo=option_repo, uow=uow)


def get_move_product_device_option_use_case(
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveProductDeviceOption:
    return MoveProductDeviceOption(option_repo=option_repo, uow=uow)


def get_product_device_kinds_use_case(
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
) -> GetProductDeviceKinds:
    return GetProductDeviceKinds(kind_repo=kind_repo)


def get_create_product_device_kind_use_case(
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateProductDeviceKind:
    return CreateProductDeviceKind(kind_repo=kind_repo, settings_repo=settings_repo, uow=uow)


def get_update_product_device_kind_use_case(
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateProductDeviceKind:
    return UpdateProductDeviceKind(kind_repo=kind_repo, settings_repo=settings_repo, uow=uow)


def get_move_product_device_kind_use_case(
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveProductDeviceKind:
    return MoveProductDeviceKind(kind_repo=kind_repo, uow=uow)


def get_set_product_device_kind_archived_use_case(
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetProductDeviceKindArchived:
    return SetProductDeviceKindArchived(kind_repo=kind_repo, uow=uow)


# ── Devices ───────────────────────────────────────────────────────────


def get_product_device_assembler(
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
) -> ProductDeviceAssembler:
    return ProductDeviceAssembler(
        devices=device_repo,
        options=option_repo,
        kinds=kind_repo,
        bought_items=bought_item_repo,
    )


def get_product_devices_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
) -> GetProductDevices:
    return GetProductDevices(product_repo=product_repo, device_repo=device_repo)


def get_product_device_use_case(
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
) -> GetProductDevice:
    return GetProductDevice(device_repo=device_repo)


def get_create_product_device_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    assembler: ProductDeviceAssembler = Depends(get_product_device_assembler),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateProductDevice:
    return CreateProductDevice(product_repo=product_repo, assembler=assembler, uow=uow)


def get_update_product_device_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    assembler: ProductDeviceAssembler = Depends(get_product_device_assembler),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    check_repo: IProductDeviceCheckRepository = Depends(get_product_device_check_repo),
) -> UpdateProductDevice:
    return UpdateProductDevice(
        product_repo=product_repo, assembler=assembler, uow=uow, check_repo=check_repo
    )


def get_product_device_completeness_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    check_repo: IProductDeviceCheckRepository = Depends(get_product_device_check_repo),
    documents: IProductDocuments = Depends(get_product_documents),
) -> GetProductDeviceCompleteness:
    return GetProductDeviceCompleteness(product_repo, device_repo, check_repo, documents)


def get_set_product_device_check_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    check_repo: IProductDeviceCheckRepository = Depends(get_product_device_check_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetProductDeviceCheck:
    return SetProductDeviceCheck(product_repo, device_repo, check_repo, uow=uow)


def get_set_product_device_archived_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetProductDeviceArchived:
    return SetProductDeviceArchived(product_repo=product_repo, device_repo=device_repo, uow=uow)


def get_preview_product_device_name_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    assembler: ProductDeviceAssembler = Depends(get_product_device_assembler),
    environment_repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
) -> PreviewProductDeviceName:
    return PreviewProductDeviceName(
        product_repo=product_repo, assembler=assembler, environment_repo=environment_repo
    )


def get_product_renumber_impact_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    documents: IProductDocuments = Depends(get_product_documents),
) -> GetProductRenumberImpact:
    return GetProductRenumberImpact(
        product_repo=product_repo, device_repo=device_repo, documents=documents
    )


def get_set_product_device_image_use_case(
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    product_repo: IProductRepository = Depends(get_product_repo),
    upload_file: UploadProductFile = Depends(get_upload_product_file_use_case),
    delete_file: DeleteProductFile = Depends(get_delete_product_file_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetProductDeviceImage:
    return SetProductDeviceImage(
        device_repo=device_repo,
        product_repo=product_repo,
        upload_file=upload_file,
        delete_file=delete_file,
        uow=uow,
    )


def get_remove_product_device_image_use_case(
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    product_repo: IProductRepository = Depends(get_product_repo),
    delete_file: DeleteProductFile = Depends(get_delete_product_file_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RemoveProductDeviceImage:
    return RemoveProductDeviceImage(
        device_repo=device_repo, product_repo=product_repo, delete_file=delete_file, uow=uow
    )


def get_place_product_device_option_use_case(
    option_repo: IProductDeviceOptionRepository = Depends(get_product_device_option_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceProductDeviceOption:
    return PlaceProductDeviceOption(option_repo=option_repo, uow=uow)


def get_place_product_device_kind_use_case(
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceProductDeviceKind:
    return PlaceProductDeviceKind(kind_repo=kind_repo, uow=uow)
