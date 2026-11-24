"""
The list of external work other modules and the read tier read: the
positions that go to a supplier for an outside process with their dates
and alerts, as the procurement tab shows them. The infoscreen widget of
the same name reads it.
"""

from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkPageResult
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkQuery
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkRowResult
from src.modules.fulfillment.application.use_cases.external_work.get_external_work import (
    GetExternalWork,
)
from src.modules.fulfillment.domain.value_objects.external_work import ExternalWorkAlert
from src.modules.fulfillment.domain.value_objects.external_work import ExternalWorkStage

__all__ = [
    "ExternalWorkAlert",
    "ExternalWorkPageResult",
    "ExternalWorkQuery",
    "ExternalWorkRowResult",
    "ExternalWorkStage",
    "GetExternalWork",
]
