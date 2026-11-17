"""Document categories of a supplier's offer on a quote request: the offer
itself and any other document that came with it. Both accumulate."""

from enum import Enum
from enum import unique


@unique
class QuoteFileCategory(str, Enum):
    OFFER = "offer"  # the supplier's offer document
    GENERAL = "general"  # anything else the supplier sent along

    @classmethod
    def singletons(cls) -> set["QuoteFileCategory"]:
        return set()

    def is_singleton(self) -> bool:
        return self in self.singletons()
