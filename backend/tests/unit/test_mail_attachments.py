"""
Attachments of composed mails: the size limit names the files that do not
fit, the SMTP message carries each attachment under its file name, and the
custom mail refuses attachments over the admin limit before sending.
"""

import base64

import pytest

from src.modules.platform.adapters.outbound.external.mail.smtp_mail_service import custom_message
from src.modules.platform.application.services.custom_mail import CustomMail
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import MailAttachmentsTooLargeError
from src.modules.platform.domain.services.mail_attachment_policy import BYTES_PER_MB
from src.modules.platform.domain.services.mail_attachment_policy import assert_attachments_fit
from src.modules.platform.domain.services.mail_attachment_policy import attachments_left_out
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories
from tests.integration.fakes import FakeLoginAttemptTracker


class TestPolicy:
    def test_the_files_after_the_limit_are_left_out_in_order(self):
        files = [
            ("notes.pdf", 4 * BYTES_PER_MB),
            ("a.pdf", 5 * BYTES_PER_MB),
            ("b.pdf", BYTES_PER_MB),
        ]

        assert attachments_left_out(files, 9 * BYTES_PER_MB) == ["b.pdf"]
        assert attachments_left_out(files, 6 * BYTES_PER_MB) == ["a.pdf"]

    def test_over_the_limit_the_refusal_names_what_does_not_fit(self):
        files = [("notes.pdf", 4 * BYTES_PER_MB), ("drawing.pdf", 7 * BYTES_PER_MB)]

        assert_attachments_fit(files[:1], 10)
        with pytest.raises(MailAttachmentsTooLargeError, match=r"drawing\.pdf \(7\.0 MB\)"):
            assert_attachments_fit(files, 10)


class TestMessage:
    def test_a_mail_without_attachments_stays_a_plain_html_mail(self):
        message = custom_message("<p>Hi</p>", [])

        assert message.get_content_subtype() == "alternative"

    def test_each_attachment_is_a_part_with_its_name_and_type(self):
        message = custom_message(
            "<p>Hi</p>",
            [
                MailAttachment("Minutes.pdf", "application/pdf", b"%PDF-1.7"),
                MailAttachment("photo.png", "image/png", b"\x89PNG"),
            ],
        )

        parts = message.get_payload()
        assert message.get_content_subtype() == "mixed"
        assert isinstance(parts, list) and len(parts) == 3
        assert parts[1].get_content_type() == "application/pdf"
        assert parts[1].get_filename() == "Minutes.pdf"
        assert base64.b64decode(parts[1].get_payload()) == b"%PDF-1.7"
        assert parts[2].get_content_type() == "image/png"


class _Mail:
    def __init__(self) -> None:
        self.sent: list[list[MailAttachment] | None] = []

    async def send_custom(self, to, subject, html_body, cc=None, reply_to=None, attachments=None):
        self.sent.append(attachments)


class _Settings:
    async def get_mail(self) -> AdminMailSettings:
        return AdminMailSettings(
            id=1,
            enabled=True,
            host="smtp.example.com",
            port=587,
            user="noreply",
            password=None,
            from_address=None,
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=20,
            send_lock_minutes=60,
            alert_recipients=[],
            attachment_limit_mb=1,
        )


def _sender() -> User:
    return factories.make_user(permissions=[Permission.SEND_MAIL])


class TestCustomMail:
    async def test_attachments_over_the_limit_are_refused_before_sending(self):
        mail = _Mail()
        custom = CustomMail(mail, FakeLoginAttemptTracker(), _Settings())  # type: ignore[arg-type]
        big = MailAttachment("big.pdf", "application/pdf", b"0" * (BYTES_PER_MB + 1))

        with pytest.raises(MailAttachmentsTooLargeError, match=r"big\.pdf"):
            await custom.send(_sender(), "a@example.com", "S", "<p>x</p>", attachments=[big])

        await custom.send(_sender(), "a@example.com", "S", "<p>x</p>")
        assert mail.sent == [None]
