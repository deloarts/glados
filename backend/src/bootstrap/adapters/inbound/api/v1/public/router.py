"""
Aggregates unauthenticated endpoints under /api/v1/public. These are reachable
without a Bearer token, only put endpoints here that are safe to expose
pre-authentication (e.g. branding shown on the login screen).
"""

from fastapi import APIRouter

from src.modules.platform.adapters.inbound.api.schemas.error_schema import PUBLIC_ERRORS
from src.modules.platform.adapters.inbound.api.v1.public.endpoints import branding
from src.modules.platform.const import API_PUBLIC

router = APIRouter(responses=PUBLIC_ERRORS)

router.include_router(branding.router, prefix=API_PUBLIC, tags=["public/branding"])
