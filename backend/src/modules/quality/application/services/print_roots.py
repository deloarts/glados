"""
Turns a print root (an order, a lot, an item, a completion, ...) into the
data a print template renders. The roots belong to Catalogue and Planning &
fulfillment, so the read tier resolves them
(src/read/application/services/print_root_resolver.py) and Quality &
documents, which prints them, owns only this protocol.
"""

from typing import Protocol

from pydantic import BaseModel


class IPrintRootResolver(Protocol):
    async def resolve(self, root_type: str, root_id: int) -> BaseModel | None:
        """The root's data, or None when there is no such root."""
        ...
