"""
What Catalogue needs to know about a machine named as an inspection method's
default: that it exists and is a QA machine, and its name for the error.
Planning & fulfillment owns the machines; its machine repository answers
this port as it is, so Catalogue never imports it.
"""

from typing import Protocol


class DefaultMachineCandidate(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def internal_name(self) -> str: ...

    @property
    def is_qa_machine(self) -> bool: ...


class IDefaultMachineLookup(Protocol):
    async def get_by_id(self, id: int) -> DefaultMachineCandidate | None:
        """The machine with this id, or None when there is none."""
        ...
