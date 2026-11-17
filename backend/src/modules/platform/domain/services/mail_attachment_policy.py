"""
The attachments of one composed mail have a total size limit, an admin mail
setting, since mail servers refuse or silently drop larger mails. Files are
taken in the order given, so the first ones, such as the PDF of the notes,
are the ones that fit, and the message of a refusal names those that do not.
"""

from collections.abc import Sequence

from src.modules.platform.domain.exceptions import MailAttachmentsTooLargeError

BYTES_PER_MB = 1024 * 1024


def megabytes(size: int) -> str:
    return f"{size / BYTES_PER_MB:.1f} MB"


def attachments_left_out(files: Sequence[tuple[str, int]], limit_bytes: int) -> list[str]:
    """The names of the files, each given with its size in bytes, that no
    longer fit once the ones before them are attached."""
    total = 0
    left_out: list[str] = []
    for name, size in files:
        if total + size > limit_bytes:
            left_out.append(name)
            continue
        total += size
    return left_out


def assert_attachments_fit(files: Sequence[tuple[str, int]], limit_mb: int) -> None:
    """Refuses attachments whose total size is over the limit, naming the
    files that do not fit."""
    limit_bytes = limit_mb * BYTES_PER_MB
    total = sum(size for _, size in files)
    if total <= limit_bytes:
        return
    sizes = dict(files)
    left_out = attachments_left_out(files, limit_bytes)
    named = ", ".join(f"{name} ({megabytes(sizes[name])})" for name in left_out)
    raise MailAttachmentsTooLargeError(
        f"The attachments come to {megabytes(total)}, more than the {limit_mb} MB a mail may "
        f"carry. These do not fit: {named}."
    )
