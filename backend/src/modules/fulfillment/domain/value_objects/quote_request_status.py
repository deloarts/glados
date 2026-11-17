"""
Status of a quote request (RFQ) and the state of each of its lines.

A quote request asks several suppliers for an offer on the same lines before
anything is ordered. Its status is derived from its own intents and line
states (src/modules/fulfillment/domain/services/lifecycle/quote_request.py); a line stays awarded
only while an order line its award created is live, so the lifecycle
reconciler derives the request again when such an order line changes.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class QuoteRequestStatus(StrValueEnum):
    """DRAFT until a supplier was sent the request, SENT while lines wait for
    an award, AWARDED once every line is awarded or dropped and one was
    awarded, CLOSED once someone closed it or dropped every line, CANCELED
    once someone canceled it."""

    DRAFT = "draft"
    SENT = "sent"
    AWARDED = "awarded"
    CLOSED = "closed"
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "QuoteRequestStatus":
        return cls.DRAFT


@unique
class QuoteRequestLineState(StrValueEnum):
    """OPEN until the line is awarded to a supplier or dropped."""

    OPEN = "open"
    AWARDED = "awarded"
    DROPPED = "dropped"


@unique
class QuoteRequestDemandFamily(StrValueEnum):
    """The demand family a line's demand share belongs to. Made item demands
    take no share: a MADE line asks for a lot position, whose lot covers
    them."""

    BOUGHT = "bought"
    SOURCE = "source"
