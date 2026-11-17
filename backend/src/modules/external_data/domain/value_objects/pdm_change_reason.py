"""
Why a caller of the change-notification trigger says a PDM file changed:
`state_change` for a workflow transition, `check_in`, `delete`, `move`,
`rename`, `add` for a file that arrived in the vault already checked in (a
task's output, an import), `copy` for a copy of a file, and `resync` for a
user who asked for a refresh by hand. The
vault add-in sends it per file, together with the destination state name
for a state change, and the single-file refresh records both on its sync
run, so the add-in's file history can say what happened in the vault and
not only that Glados was asked. It is a label and nothing more: Glados
re-reads the file whatever the reason, and a caller that sends none gets
the same refresh.
"""

from enum import Enum
from enum import unique


@unique
class PdmChangeReason(str, Enum):
    STATE_CHANGE = "state_change"
    CHECK_IN = "check_in"
    DELETE = "delete"
    MOVE = "move"
    RENAME = "rename"
    RESYNC = "resync"
    ADD = "add"
    COPY = "copy"
