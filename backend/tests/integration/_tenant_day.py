"""
The current day in the tenant's default timezone, the day completions and
scraps are booked on and checked against. Read when called, so a test that
runs across midnight uses the day of its request.
"""

from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE


def tenant_today() -> date:
    return datetime.now(ZoneInfo(SERVER_DEFAULT_TIMEZONE)).date()
