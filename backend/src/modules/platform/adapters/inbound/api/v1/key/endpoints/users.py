"""
API key surface user endpoint.
Exposes RFID-based user lookup for hardware clients (RFID readers, etc.).
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.deps.auth import get_identify_user_by_rfid_use_case
from src.modules.platform.adapters.inbound.api.schemas.rfid_schema import RfidIdentityResponse
from src.modules.platform.adapters.inbound.api.schemas.rfid_schema import RfidLookupRequest
from src.modules.platform.application.dto.user_dto import RfidIdentityResult
from src.modules.platform.application.use_cases.user.identify_user_by_rfid import IdentifyUserByRfid

router = APIRouter()


@router.post("/rfid", response_model=RfidIdentityResponse)
async def identify_user_by_rfid(
    body: RfidLookupRequest,
    use_case: IdentifyUserByRfid = Depends(get_identify_user_by_rfid_use_case),
    # API key auth is checked at the router level via a dependency on the router itself
) -> RfidIdentityResult:
    """
    Look up who an RFID tag belongs to, for hardware readers without a web
    session. Returns the id, username and full name only.

    403 while the admin security setting `allow_rfid_login` is off, 404 for
    an unknown tag or an inactive account.
    """
    return await use_case.execute(body.rfid)
