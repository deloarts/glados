"""
The requests that reorder an entry of a hand-ordered list, such as an
article group or a production machine: one place up or down, or next to a
named neighbour, which is what dragging a row does.
"""

from pydantic import BaseModel
from pydantic import model_validator

from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


class ListMoveRequest(BaseModel):
    direction: ListMoveDirection


class ListPlaceRequest(BaseModel):
    """Directly after `after_id`, or directly before `before_id` when the
    row was dropped at the top of the page. Neither puts it first."""

    after_id: int | None = None
    before_id: int | None = None

    @model_validator(mode="after")
    def _one_neighbour(self) -> "ListPlaceRequest":
        if self.after_id is not None and self.before_id is not None:
            raise ValueError("Name either after_id or before_id, not both.")
        return self
