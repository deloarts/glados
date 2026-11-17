"""
The edit version of a master data row (items, products, devices, suppliers,
customers), shared by every table whose edit form sends back the version it
read. A model mixes in EditVersionColumn and lists in
`__edit_version_ignored__` the bookkeeping columns whose change alone must
not move the version, such as a sync timestamp no form shows.

Nobody moves the version by hand. The session listener in
`persistence/edit_version_tracking.py` moves it whenever a flush changes the
row, whoever writes it: a web form, the `pat` API, a PDM ingest or a merge.
"""

from typing import ClassVar

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class EditVersionColumn:
    # Columns whose change alone leaves the edit version where it is.
    __edit_version_ignored__: ClassVar[frozenset[str]] = frozenset()

    edit_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
