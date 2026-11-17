"""
The lifecycle of a project as the use cases run it: the user actions its
intent table accepts and the status moves they make. Readers outside this
module, such as the state machine catalogue of the handbook, describe the
lifecycle from these objects and never change them.
"""

from src.modules.workspace.domain.services.lifecycle.project import PROJECT_INTENTS
from src.modules.workspace.domain.services.lifecycle.project import PROJECT_STATUS_MOVES

__all__ = ["PROJECT_INTENTS", "PROJECT_STATUS_MOVES"]
