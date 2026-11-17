"""
Read access to the EPLAN Data Portal. The application layer calls this,
never httpx directly; the implementation lives in
src/modules/external_data/adapters/outbound/external/eplan_data_portal/. Every call is
authenticated with the organisation's personal access token from the
settings. Errors are the domain's Edp* exceptions: unreachable portal
(EdpUnavailableError), rejected token (EdpAuthenticationFailedError),
anything else it got wrong (EdpProviderError).
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpConnectionInfo
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpNumberMatch
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart


@dataclass(frozen=True)
class EdpConnection:
    base_url: str
    pat: str = field(repr=False)


@runtime_checkable
class IEplanDataPortal(Protocol):
    async def test_connection(self) -> EdpConnectionInfo:
        """An authenticated request that proves the token is accepted."""
        ...

    async def check_numbers(self, numbers: list[str]) -> list[EdpNumberMatch]:
        """Exact lookup of order, type or EPLAN part numbers, one match per
        number in the order given."""
        ...

    async def search(self, query: str, limit: int) -> list[EdpPart]:
        """Ranked full-text search, the best `limit` hits."""
        ...

    async def get_parts(self, part_ids: list[int]) -> list[EdpPart]:
        """The parts with these ids, with manufacturer, product groups,
        documents and picture resolved. Unknown ids are left out."""
        ...

    async def fetch_picture(self, url: str) -> bytes | None:
        """The picture behind a part's picture_url, None when it is gone."""
        ...


class IEplanDataPortalFactory(Protocol):
    def __call__(self, connection: EdpConnection) -> IEplanDataPortal: ...
