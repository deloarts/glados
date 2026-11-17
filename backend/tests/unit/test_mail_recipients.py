"""
Several recipients in the To field of a user-composed mail: how the text
is split, how the request validates it, and that the SMTP envelope carries
every address.
"""

import pytest
from pydantic import ValidationError

from src.modules.platform.adapters.inbound.api.schemas.mail_schema import SendMailRequest
from src.modules.platform.domain.services.mail_recipients import MAX_MAIL_RECIPIENTS
from src.modules.platform.domain.services.mail_recipients import split_mail_recipients


def test_split_trims_and_drops_empty_and_repeated_entries() -> None:
    assert split_mail_recipients(" a@x.com, b@x.com;;a@x.com ,") == ["a@x.com", "b@x.com"]


def test_a_single_address_stays_one() -> None:
    assert split_mail_recipients("a@x.com") == ["a@x.com"]


def _request(to: str) -> SendMailRequest:
    return SendMailRequest(to=to, subject="Order", html_body="<p>hi</p>")


def test_the_request_joins_valid_addresses_with_commas() -> None:
    assert _request("karin@example.com; martin@example.com").to == (
        "karin@example.com, martin@example.com"
    )


@pytest.mark.parametrize(
    "to",
    ["", " , ", "karin@example.com, not-an-address"],
)
def test_the_request_refuses_a_missing_or_wrong_address(to: str) -> None:
    with pytest.raises(ValidationError):
        _request(to)


def test_the_request_refuses_too_many_recipients() -> None:
    to = ", ".join(f"person{i}@example.com" for i in range(MAX_MAIL_RECIPIENTS + 1))

    with pytest.raises(ValidationError):
        _request(to)
