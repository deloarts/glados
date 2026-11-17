"""
A file attached to a user-composed mail, such as the PDF of meeting notes
and the documents of the meeting sent along with it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MailAttachment:
    file_name: str
    content_type: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)
