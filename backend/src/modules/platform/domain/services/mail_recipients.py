"""
The To field of a user-composed mail may name several recipients, such as
every contact of a supplier who receives its order mails. They are written
as one text, separated by commas or semicolons.
"""

# A composed mail reaches a handful of people; more would look like a mass mail.
MAX_MAIL_RECIPIENTS = 20


def split_mail_recipients(value: str) -> list[str]:
    """The addresses of a recipient text, trimmed, without empty entries and
    duplicates, in the order written."""
    parts = (part.strip() for part in value.replace(";", ",").split(","))
    return list(dict.fromkeys(part for part in parts if part))
