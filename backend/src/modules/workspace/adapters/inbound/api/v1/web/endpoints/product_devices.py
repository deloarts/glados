"""
Endpoints for the devices of a product. `router` is mounted under
/products and holds the routes that start from a product: list, create,
name preview, and what renumbering the product would affect.
`device_router` is mounted under /product-devices and holds the routes on
one device, including uploading its two images. Devices are archived,
never deleted.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_create_manual_plc_tag_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_delete_manual_plc_tag_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_product_plc_tags_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_set_signal_tag_name_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.plc_environments import (
    get_update_manual_plc_tag_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_create_product_device_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_preview_product_device_name_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_completeness_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_devices_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_renumber_impact_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_remove_product_device_image_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_set_product_device_archived_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_set_product_device_check_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_set_product_device_image_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_update_product_device_use_case,
)
from src.modules.workspace.adapters.inbound.api.schemas.plc_environment_schema import (
    ManualPlcTagSaveRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.plc_environment_schema import (
    PlcTagListResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.plc_environment_schema import (
    SignalTagNameRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceCheckRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceCheckResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceCompletenessResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceNamePreviewRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceNamePreviewResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceSaveRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceUpdateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import (
    ProductRenumberImpactResponse,
)
from src.modules.workspace.application.dto.plc_tag_dto import SaveManualPlcTagCommand
from src.modules.workspace.application.dto.plc_tag_dto import SetSignalTagNameCommand
from src.modules.workspace.application.dto.product_device_dto import PreviewProductDeviceNameCommand
from src.modules.workspace.application.dto.product_device_dto import SaveProductDeviceCommand
from src.modules.workspace.application.use_cases.plc_environment.tags import CreateManualPlcTag
from src.modules.workspace.application.use_cases.plc_environment.tags import DeleteManualPlcTag
from src.modules.workspace.application.use_cases.plc_environment.tags import GetProductPlcTags
from src.modules.workspace.application.use_cases.plc_environment.tags import SetSignalTagName
from src.modules.workspace.application.use_cases.plc_environment.tags import UpdateManualPlcTag
from src.modules.workspace.application.use_cases.product.get_renumber_impact import (
    GetProductRenumberImpact,
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
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.modules.workspace.domain.value_objects.product_device_image_slot import (
    ProductDeviceImageSlot,
)

router = APIRouter()
device_router = APIRouter()
# Manual PLC tags, mounted under /plc-manual-tags.
manual_tag_router = APIRouter()


@router.get("/{product_id}/devices", response_model=list[ProductDeviceResponse])
async def read_product_devices(
    product_id: int,
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_active_user),
    use_case: GetProductDevices = Depends(get_product_devices_use_case),
) -> list[ProductDeviceResponse]:
    results = await use_case.execute(product_id, include_archived)
    return [ProductDeviceResponse.model_validate(r.model_dump()) for r in results]


@router.post(
    "/{product_id}/devices",
    response_model=ProductDeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_device(
    product_id: int,
    body: ProductDeviceSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProductDevice = Depends(get_create_product_device_use_case),
) -> ProductDeviceResponse:
    result = await use_case.execute(
        actor, product_id, SaveProductDeviceCommand(**body.model_dump())
    )
    return ProductDeviceResponse.model_validate(result.model_dump())


@router.post("/{product_id}/devices/name-preview", response_model=ProductDeviceNamePreviewResponse)
async def preview_product_device_name(
    product_id: int,
    body: ProductDeviceNamePreviewRequest,
    _: User = Depends(get_current_active_user),
    use_case: PreviewProductDeviceName = Depends(get_preview_product_device_name_use_case),
) -> ProductDeviceNamePreviewResponse:
    result = await use_case.execute(
        product_id, PreviewProductDeviceNameCommand(**body.model_dump())
    )
    return ProductDeviceNamePreviewResponse.model_validate(result.model_dump())


@router.get("/{product_id}/plc-tags", response_model=PlcTagListResponse)
async def read_product_plc_tags(
    product_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductPlcTags = Depends(get_product_plc_tags_use_case),
) -> PlcTagListResponse:
    """The product's PLC tags for its PLC environment, built from its live devices."""
    result = await use_case.execute(product_id)
    return PlcTagListResponse.model_validate(result.model_dump())


@router.post("/{product_id}/plc-tags/manual", status_code=status.HTTP_201_CREATED)
async def create_manual_plc_tag(
    product_id: int,
    body: ManualPlcTagSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateManualPlcTag = Depends(get_create_manual_plc_tag_use_case),
) -> dict[str, int]:
    """Adds a tag that belongs to no device; the list shows it with the others."""
    tag_id = await use_case.execute(actor, product_id, SaveManualPlcTagCommand(**body.model_dump()))
    return {"id": tag_id}


@router.get(
    "/{product_id}/device-completeness", response_model=list[ProductDeviceCompletenessResponse]
)
async def read_product_device_completeness(
    product_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductDeviceCompleteness = Depends(get_product_device_completeness_use_case),
) -> list[ProductDeviceCompletenessResponse]:
    """Per live device: the plans it is ticked as drawn in, and its sequence coverage."""
    results = await use_case.execute(product_id)
    return [
        ProductDeviceCompletenessResponse(
            device_id=r.device_id,
            checks=[
                ProductDeviceCheckResponse(
                    plan=c.plan, checked_by_name=c.checked_by_name, checked_at=c.checked_at
                )
                for c in r.checks
            ],
            sequence_coverage=r.sequence_coverage,
        )
        for r in results
    ]


@router.get("/{product_id}/renumber-impact", response_model=ProductRenumberImpactResponse)
async def read_product_renumber_impact(
    product_id: int,
    new_number: str = Query(min_length=1, max_length=200),
    _: User = Depends(get_current_active_user),
    use_case: GetProductRenumberImpact = Depends(get_product_renumber_impact_use_case),
) -> ProductRenumberImpactResponse:
    result = await use_case.execute(product_id, new_number)
    return ProductRenumberImpactResponse.model_validate(result.model_dump())


@device_router.get("/{device_id}", response_model=ProductDeviceResponse)
async def read_product_device(
    device_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductDevice = Depends(get_product_device_use_case),
) -> ProductDeviceResponse:
    result = await use_case.execute(device_id)
    return ProductDeviceResponse.model_validate(result.model_dump())


@device_router.put("/{device_id}", response_model=ProductDeviceResponse)
async def update_product_device(
    device_id: int,
    body: ProductDeviceUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductDevice = Depends(get_update_product_device_use_case),
) -> ProductDeviceResponse:
    result = await use_case.execute(actor, device_id, SaveProductDeviceCommand(**body.model_dump()))
    return ProductDeviceResponse.model_validate(result.model_dump())


@device_router.post("/{device_id}/archive", response_model=ProductDeviceResponse)
async def archive_product_device(
    device_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceArchived = Depends(get_set_product_device_archived_use_case),
) -> ProductDeviceResponse:
    result = await use_case.execute(actor, device_id, archived=True)
    return ProductDeviceResponse.model_validate(result.model_dump())


@device_router.post("/{device_id}/restore", response_model=ProductDeviceResponse)
async def restore_product_device(
    device_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceArchived = Depends(get_set_product_device_archived_use_case),
) -> ProductDeviceResponse:
    result = await use_case.execute(actor, device_id, archived=False)
    return ProductDeviceResponse.model_validate(result.model_dump())


@device_router.post(
    "/{device_id}/images/{slot}",
    response_model=ProductDeviceResponse,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def set_product_device_image(
    device_id: int,
    slot: ProductDeviceImageSlot,
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceImage = Depends(get_set_product_device_image_use_case),
) -> ProductDeviceResponse:
    """Uploads the device's rendering or parent assembly rendering,
    replacing the one the slot had."""
    data, _file_name, content_type = await read_upload(file)
    result = await use_case.execute(actor, device_id, slot, data, content_type)
    return ProductDeviceResponse.model_validate(result.model_dump())


@device_router.delete("/{device_id}/images/{slot}", response_model=ProductDeviceResponse)
async def remove_product_device_image(
    device_id: int,
    slot: ProductDeviceImageSlot,
    actor: User = Depends(get_current_active_user),
    use_case: RemoveProductDeviceImage = Depends(get_remove_product_device_image_use_case),
) -> ProductDeviceResponse:
    result = await use_case.execute(actor, device_id, slot)
    return ProductDeviceResponse.model_validate(result.model_dump())


@manual_tag_router.put("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_manual_plc_tag(
    tag_id: int,
    body: ManualPlcTagSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateManualPlcTag = Depends(get_update_manual_plc_tag_use_case),
) -> None:
    await use_case.execute(actor, tag_id, SaveManualPlcTagCommand(**body.model_dump()))


@manual_tag_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual_plc_tag(
    tag_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteManualPlcTag = Depends(get_delete_manual_plc_tag_use_case),
) -> None:
    await use_case.execute(actor, tag_id)


@device_router.put("/{device_id}/signal-tag-name", status_code=status.HTTP_204_NO_CONTENT)
async def set_signal_tag_name(
    device_id: int,
    body: SignalTagNameRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetSignalTagName = Depends(get_set_signal_tag_name_use_case),
) -> None:
    """Gives one signal of the device a PLC tag name of its own, or takes it off."""
    await use_case.execute(actor, device_id, SetSignalTagNameCommand(**body.model_dump()))


@device_router.put("/{device_id}/checks/{plan}", status_code=status.HTTP_204_NO_CONTENT)
async def set_product_device_check(
    device_id: int,
    plan: DevicePlan,
    body: ProductDeviceCheckRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceCheck = Depends(get_set_product_device_check_use_case),
) -> None:
    """Ticks or unticks that the device is drawn in a plan."""
    await use_case.execute(actor, device_id, plan, body.checked)
