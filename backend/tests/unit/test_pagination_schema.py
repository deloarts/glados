"""
PageResponse.from_result, which every plain list endpoint returns through,
and PageParams, the paging fields list filters inherit.
"""

from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse


class _Dto(BaseModel):
    id: int
    name: str


class _Wire(BaseModel):
    name: str


class _Result:
    def __init__(self, total: int, items: list[_Dto]) -> None:
        self.total = total
        self.items = items


class _Params(PageParams):
    search: str | None = None


def test_from_result_echoes_the_request_paging() -> None:
    items = [_Dto(id=1, name="a")]

    page = PageResponse.from_result(_Result(9, items), _Params(skip=20, limit=10))

    assert page.model_dump() == {
        "items": [{"id": 1, "name": "a"}],
        "total": 9,
        "limit": 10,
        "skip": 20,
    }


def test_from_result_reports_skip_zero_and_no_limit_when_omitted() -> None:
    page = PageResponse.from_result(_Result(0, []), _Params())

    assert (page.skip, page.limit, page.items) == (0, None, [])


def test_from_result_revalidates_items_into_the_item_model() -> None:
    page = PageResponse.from_result(_Result(1, [_Dto(id=3, name="b")]), _Params(), item_model=_Wire)

    assert page.items == [_Wire(name="b")]
    assert type(page.items[0]) is _Wire


def test_page_params_come_first_in_a_filter() -> None:
    assert list(_Params.model_fields) == ["skip", "limit", "search"]
