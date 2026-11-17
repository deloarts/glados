"""Aggregates PAT (Personal Access Token) API endpoints under /api/pat; routes requests
to catalogue and settings sub-resources for programmatic access.

Every pat request first sets the label languages (see label_languages.py) to
the add-in language from the PDM settings, then the tenant's default
language, so catalogue labels in any pat response come back as one string in
the language the SolidWorks add-in writes into the vault. It lives here, in
the composition root, because the PDM settings belong to external data while
the labels are served by catalogue endpoints.
"""

from fastapi import APIRouter
from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import article_groups
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import bought_items
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import fabrication_methods
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import inspection_methods
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import lookups
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import made_items
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import source_item_types
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import source_items
from src.modules.catalogue.adapters.inbound.api.v1.pat.endpoints import suppliers
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_external_data_settings_repo,
)
from src.modules.external_data.adapters.inbound.api.v1.pat.endpoints import bought_items_edp
from src.modules.external_data.adapters.inbound.api.v1.pat.endpoints import pdm
from src.modules.external_data.adapters.inbound.api.v1.pat.endpoints import settings
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.schemas.error_schema import AUTHENTICATED_ERRORS
from src.modules.platform.adapters.inbound.api.v1.pat.endpoints import users
from src.modules.platform.adapters.inbound.api.v1.pat.endpoints import version
from src.modules.platform.const import API_PAT
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.infrastructure.label_languages import set_label_languages
from src.modules.workspace.adapters.inbound.api.v1.pat.endpoints import products
from src.modules.workspace.adapters.inbound.api.v1.pat.endpoints import projects


async def use_addin_label_languages(
    settings: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> None:
    addin_language = (await settings.get_pdm()).addin_language
    tenant_language = (await settings.get_general()).default_language.value
    set_label_languages(
        [addin_language if addin_language in Language.values() else None, tenant_language]
    )


router = APIRouter(
    dependencies=[Depends(use_addin_label_languages)], responses=AUTHENTICATED_ERRORS
)

router.include_router(
    bought_items.router, prefix=f"{API_PAT}/bought-items", tags=["pat/bought-items"]
)
router.include_router(
    bought_items_edp.router,
    prefix=f"{API_PAT}/bought-items-edp",
    tags=["pat/bought-items-edp"],
)
router.include_router(products.router, prefix=f"{API_PAT}/products", tags=["pat/products"])
router.include_router(projects.router, prefix=f"{API_PAT}/projects", tags=["pat/projects"])
router.include_router(suppliers.router, prefix=f"{API_PAT}/suppliers", tags=["pat/suppliers"])
router.include_router(
    article_groups.router, prefix=f"{API_PAT}/article-groups", tags=["pat/article-groups"]
)
router.include_router(
    fabrication_methods.router,
    prefix=f"{API_PAT}/fabrication-methods",
    tags=["pat/fabrication-methods"],
)
router.include_router(
    inspection_methods.router,
    prefix=f"{API_PAT}/inspection-methods",
    tags=["pat/inspection-methods"],
)
router.include_router(made_items.router, prefix=f"{API_PAT}/made-items", tags=["pat/made-items"])
router.include_router(pdm.router, prefix=f"{API_PAT}/pdm", tags=["pat/pdm"])
router.include_router(
    source_item_types.router, prefix=f"{API_PAT}/source-item-types", tags=["pat/source-item-types"]
)
router.include_router(
    source_items.router, prefix=f"{API_PAT}/source-items", tags=["pat/source-items"]
)
router.include_router(settings.router, prefix=f"{API_PAT}/settings", tags=["pat/settings"])
router.include_router(users.router, prefix=f"{API_PAT}/users", tags=["pat/users"])
router.include_router(lookups.router, prefix=f"{API_PAT}/lookups", tags=["pat/lookups"])
router.include_router(version.router, prefix=API_PAT, tags=["pat/version"])
