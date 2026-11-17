"""The status transitions of the lifecycles, as the code makes them.

An ObservedTransition is one status change the lifecycle model saw a real use
case make: the machine whose status changed (a state machine catalogue key),
the status before and after, the request that made it (the method of the
model's world that ran the use case) and the machine of the aggregate that
request acted on. A transition on another aggregate's machine than the
subject's is an implication of the request, a cascade. The set itself is
generated (observed_transitions.py), never written by hand.
"""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class ObservedTransition:
    machine: str
    # None when the request created the aggregate.
    from_state: str | None
    to_state: str
    trigger: str
    subject: str
