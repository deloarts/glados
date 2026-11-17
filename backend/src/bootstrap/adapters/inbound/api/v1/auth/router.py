"""
Aggregates authentication endpoints for all client surfaces under
/api/v1/auth. Each endpoint keeps the tag of its surface (web/auth,
pat/auth) so it still shows up on that surface's Swagger UI page, see
src/modules/platform/adapters/inbound/api/docs.py.

Note there is deliberately no RFID endpoint here. RFID identifies, it does
not authenticate: a chip is cloneable and readable at a distance, so it is
not a credential. Operator identification lives behind a real session at
POST /api/v1/web/production-operators/identify.
"""

from fastapi import APIRouter

from src.modules.platform.adapters.inbound.api.v1.auth.endpoints import logout
from src.modules.platform.adapters.inbound.api.v1.auth.endpoints import passkey_login
from src.modules.platform.adapters.inbound.api.v1.auth.endpoints import pat_login
from src.modules.platform.adapters.inbound.api.v1.auth.endpoints import totp_login
from src.modules.platform.adapters.inbound.api.v1.auth.endpoints import web_login
from src.modules.platform.const import API_AUTH

router = APIRouter()

router.include_router(web_login.router, prefix=API_AUTH, tags=["web/auth"])
router.include_router(totp_login.router, prefix=API_AUTH, tags=["web/auth"])
router.include_router(passkey_login.router, prefix=API_AUTH, tags=["web/auth"])
router.include_router(logout.router, prefix=API_AUTH, tags=["web/auth"])
router.include_router(pat_login.router, prefix=API_AUTH, tags=["pat/auth"])
