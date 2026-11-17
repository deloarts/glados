"""
How urgent an admin-authored announcement (banner or acknowledgement) is.
Wire vocabulary only: the frontend maps this onto OpenVue's own severity
names (info/warn/error) rather than the API adopting OpenVue's vocabulary
directly, so the wire contract stays independent of one UI library's
naming.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class AnnouncementSeverity(StrValueEnum):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"

    @classmethod
    def default(cls) -> "AnnouncementSeverity":
        return cls.INFO
