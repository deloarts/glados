"""Vocabulary and limits of a message to terminals: a one-time Markdown
text shown on many displays at once until a given moment. The text is
stored as typed and rendered on the display."""

from datetime import timedelta
from enum import unique
from typing import Final

from src.modules.operations.domain.value_objects.infoscreen import MAX_MESSAGE_LENGTH
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class TerminalBroadcastSeverity(StrValueEnum):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


@unique
class TerminalBroadcastStyle(StrValueEnum):
    # A bar above the screen.
    BANNER = "banner"
    # Over the whole screen.
    FULLSCREEN = "fullscreen"


# The cap of a message widget's text, enough for a few lines of Markdown.
MAX_BROADCAST_TEXT_LENGTH: Final = MAX_MESSAGE_LENGTH
# How far ahead a message may end.
MAX_BROADCAST_DURATION: Final = timedelta(days=30)
# Terminals or infoscreens one message may pick.
MAX_BROADCAST_TARGETS: Final = 500
