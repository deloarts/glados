"""
When an acknowledgement's confirmation dialog is delivered to a recipient:
  - IMMEDIATELY: the live row-sync signal pops the dialog in every running
    session the recipient already has open, as soon as it is created.
  - NEXT_LOGIN: delivered only to a session created at or after the
    acknowledgement's own created_at (see
    IAcknowledgementRepository.get_pending_for_user); a session already
    open at creation time never sees it until the user signs in again.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class AcknowledgementShowWhen(StrValueEnum):
    IMMEDIATELY = "immediately"
    NEXT_LOGIN = "next_login"

    @classmethod
    def default(cls) -> "AcknowledgementShowWhen":
        return cls.IMMEDIATELY
