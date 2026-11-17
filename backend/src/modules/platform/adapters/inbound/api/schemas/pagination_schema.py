"""Generic pagination response schema used across list endpoints, and the
paging query parameters most list filters share.

`PageParams` declares `skip` and `limit` once. A filter class that
inherits it gets both as its first two query parameters, which is the
position every list filter has always declared them in, so the OpenAPI
documents do not change.
"""

from collections.abc import Sequence
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar
from typing import overload

from fastapi import Query
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE

T = TypeVar("T")
ItemT = TypeVar("ItemT", covariant=True)
ModelT = TypeVar("ModelT", bound=BaseModel)


class PageResult(Protocol[ItemT]):
    """A use case's paginated result: the matching total and one page."""

    @property
    def total(self) -> int: ...

    @property
    def items(self) -> Sequence[ItemT]: ...


class PageQuery(Protocol):
    """The paging part of a list request."""

    @property
    def skip(self) -> int | None: ...

    @property
    def limit(self) -> int | None: ...


class PageParams(BaseModel):
    skip: int | None = Query(default=None, ge=0, description="Rows to skip; 0 when omitted.")
    # The default stays None rather than DEFAULT_PAGE_SIZE: an `ids` filter
    # without a limit reads every id it names (persistence/pagination.py).
    limit: int | None = Query(
        default=None,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=(
            f"Rows per page, at most {MAX_PAGE_SIZE}; {DEFAULT_PAGE_SIZE} when omitted. "
            "`total` in the response says how many rows match."
        ),
    )


class PageResponse(ResponseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int | None
    skip: int

    @overload
    @classmethod
    def from_result(cls, result: PageResult[T], params: PageQuery) -> "PageResponse[T]": ...

    @overload
    @classmethod
    def from_result(
        cls, result: PageResult[BaseModel], params: PageQuery, *, item_model: type[ModelT]
    ) -> "PageResponse[ModelT]": ...

    @classmethod
    def from_result(
        cls,
        result: PageResult[Any],
        params: PageQuery,
        *,
        item_model: type[BaseModel] | None = None,
    ) -> "PageResponse[Any]":
        """The page of `result` for the request `params`, echoing the
        requested limit and the skip (0 when omitted). With `item_model`,
        each item is re-validated into that response model through its
        dumped fields, for result DTOs that are not the wire schema."""
        items: Any = result.items
        if item_model is not None:
            items = [item_model.model_validate(i.model_dump()) for i in result.items]
        return cls(items=items, total=result.total, limit=params.limit, skip=params.skip or 0)
