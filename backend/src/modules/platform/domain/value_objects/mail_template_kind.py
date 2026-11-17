"""
The full set of mail kinds the Localized Mail Templates engine knows about,
see src/modules/platform/domain/services/mail_template_specs.py for the family/variables/
default_subject/sample_context declared per kind. Six kinds are sent from
a direct send site (welcome, notification_digest, test_mail, request,
order, meeting_notes), the rest are event-driven.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class MailTemplateKind(StrValueEnum):
    WELCOME = "welcome"
    NOTIFICATION_DIGEST = "notification_digest"
    TEST_MAIL = "test_mail"
    REQUEST = "request"
    ORDER = "order"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    PERMISSIONS_CHANGED = "permissions_changed"
    PROJECT_ASSIGNED = "project_assigned"
    PRODUCT_ASSIGNED = "product_assigned"
    ORDER_CANCELED = "order_canceled"
    SCHEDULE_ERROR = "schedule_error"
    DISK_SPACE_WARNING = "disk_space_warning"
    SUPPLIER_LINES_TO_SETTLE = "supplier_lines_to_settle"
    MEETING_NOTES = "meeting_notes"
