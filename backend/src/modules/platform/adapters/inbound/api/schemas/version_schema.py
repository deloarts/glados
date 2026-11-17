"""HTTP schema of the `pat` version route, which tells an external client
such as the SolidWorks add-in which backend version and which `pat`
contract it talks to."""

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class PatVersionResponse(ResponseModel):
    # The full backend version, e.g. "1.2.3".
    version: str
    # The `major.minor` of the `pat` contract this backend serves, e.g.
    # "1.2". A client compares it with the minors it supports.
    pat_contract: str
