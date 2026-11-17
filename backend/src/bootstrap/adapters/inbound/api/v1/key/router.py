"""Aggregates API key authentication endpoints under /api/key; routes requests to
products, projects, and users sub-resources."""

from fastapi import APIRouter
from fastapi import Depends

from src.modules.external_data.adapters.inbound.api.v1.key.endpoints import pdm
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_api_key_user
from src.modules.platform.adapters.inbound.api.schemas.error_schema import AUTHENTICATED_ERRORS
from src.modules.platform.adapters.inbound.api.v1.key.endpoints import users
from src.modules.platform.const import API_KEY
from src.modules.workspace.adapters.inbound.api.v1.key.endpoints import products
from src.modules.workspace.adapters.inbound.api.v1.key.endpoints import projects

router = APIRouter(dependencies=[Depends(get_current_api_key_user)], responses=AUTHENTICATED_ERRORS)

router.include_router(pdm.router, prefix=f"{API_KEY}/pdm", tags=["key/pdm"])
router.include_router(products.router, prefix=f"{API_KEY}/products", tags=["key/products"])
router.include_router(projects.router, prefix=f"{API_KEY}/projects", tags=["key/projects"])
router.include_router(users.router, prefix=f"{API_KEY}/users", tags=["key/users"])
