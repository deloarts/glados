"""
Builds the feed an infoscreen or a terminal shows. The feed reads Planning &
fulfillment, Quality & documents and Catalogue, so the read tier builds it
(src/read/application/use_cases/infoscreen/build_infoscreen_feed.py) and
Operations, which serves it, owns only this protocol.
"""

from typing import Protocol

from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedResult
from src.modules.operations.domain.entities.infoscreen import Infoscreen


class IInfoscreenFeedBuilder(Protocol):
    async def execute(self, infoscreen: Infoscreen) -> InfoscreenFeedResult: ...
