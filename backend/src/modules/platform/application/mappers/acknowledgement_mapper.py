"""
Maps Acknowledgement domain entities to result DTOs.
"""

from src.modules.platform.application.dto.acknowledgement_dto import AcknowledgementRecipientResult
from src.modules.platform.application.dto.acknowledgement_dto import AcknowledgementSummaryResult
from src.modules.platform.application.dto.acknowledgement_dto import PendingAcknowledgementResult
from src.modules.platform.domain.entities.acknowledgement import Acknowledgement
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementRecipientView,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementSummary,
)


class AcknowledgementMapper:
    @staticmethod
    def summary_to_result(s: AcknowledgementSummary) -> AcknowledgementSummaryResult:
        ack = s.acknowledgement
        return AcknowledgementSummaryResult(
            id=ack.id,
            public_id=ack.public_id,
            text=ack.text,
            severity=ack.severity,
            enabled=ack.enabled,
            show_when=ack.show_when,
            created_at=ack.created_at,
            created_by_username=s.created_by_username,
            recipients_total=s.recipients_total,
            recipients_acknowledged=s.recipients_acknowledged,
        )

    @staticmethod
    def recipient_view_to_result(
        v: AcknowledgementRecipientView,
    ) -> AcknowledgementRecipientResult:
        return AcknowledgementRecipientResult(
            user_id=v.user_id,
            username=v.username,
            full_name=v.full_name,
            acknowledged_at=v.acknowledged_at,
        )

    @staticmethod
    def to_pending_result(a: Acknowledgement) -> PendingAcknowledgementResult:
        return PendingAcknowledgementResult(
            public_id=a.public_id,
            text=a.text,
            severity=a.severity,
            created_at=a.created_at,
        )
