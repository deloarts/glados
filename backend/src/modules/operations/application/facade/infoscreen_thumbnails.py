"""
The thumbnail links of an infoscreen feed, which the read tier builds: each
row that names an item links to its thumbnail through a token Operations
signs for its terminal devices.
"""

from src.modules.operations.application.services.infoscreen_thumbnails import ThumbnailLinker

__all__ = ["ThumbnailLinker"]
