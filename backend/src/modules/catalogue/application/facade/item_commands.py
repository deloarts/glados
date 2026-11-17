"""
The item commands other modules drive, such as CAD & external data's PDM
ingest and EPLAN Data Portal linking: creating, revising and updating items,
uploading their files and pictures, and building the processes of made
items. They are Catalogue's own use cases and services, published here
together with the repository ports their constructors take.
"""

from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.application.services.item_picture_store import StagedItemPicture
from src.modules.catalogue.application.services.made_item_creation import build_and_save_processes
from src.modules.catalogue.application.services.made_item_creation import validate_processes
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.upload_bought_item_file import (
    UploadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)

__all__ = [
    "CreateBoughtItem",
    "CreateMadeItem",
    "CreateMadeItemRevision",
    "IBoughtItemRepository",
    "IFabricationMethodRepository",
    "IInspectionMethodRepository",
    "IMadeItemRepository",
    "ItemPictureStore",
    "StagedItemPicture",
    "UpdateBoughtItem",
    "UploadBoughtItemFile",
    "UploadMadeItemFile",
    "build_and_save_processes",
    "validate_processes",
]
