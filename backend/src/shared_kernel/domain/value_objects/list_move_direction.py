"""The way an entry of a hand-ordered list moves when it is shifted by one
place: up towards the top, where pickers offer it first, or down."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ListMoveDirection(StrValueEnum):
    UP = "up"
    DOWN = "down"
