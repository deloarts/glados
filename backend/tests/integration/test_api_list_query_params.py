"""
Guards how the list-typed filter fields are bound. A BaseModel filter
bound via `Depends()` makes FastAPI classify its `list[...]` fields as a
request body on the GET, so `?ids=1&ids=2` arrived as None server-side,
silently disabling live row-sync's targeted refetch and the multi-status
filters. The affected endpoints bind their models as
`Annotated[Model, Query()]` instead; this pins that the list fields really
are array query parameters and that no GET in the web surface carries a
request body.
"""

import pytest

from src.bootstrap.main import app

LIST_QUERY_FIELDS = {
    "/api/v1/web/bought-items/": {"ids"},
    "/api/v1/web/bought-items-demands/": {"ids", "bucket_id", "order_id"},
    "/api/v1/web/made-items/": {"ids"},
    "/api/v1/web/made-items-demands/": {
        "ids",
        "statuses",
        "bucket_id",
        "lot_id",
        "process_fabrication_method_id",
        "process_inspection_method_id",
    },
    "/api/v1/web/source-items/": {"ids"},
    "/api/v1/web/source-item-demands/": {"ids", "bucket_id", "lot_id", "order_id"},
    "/api/v1/web/production-lots/": {"ids", "statuses"},
    "/api/v1/web/admin/settings/pdm/runs": {"trigger"},
    "/api/v1/web/production-qa/": {"status", "inspection_method_id", "finished_by_id"},
}


@pytest.fixture
def spec():
    return app.openapi()


@pytest.mark.parametrize(("path", "fields"), sorted(LIST_QUERY_FIELDS.items()))
def test_list_filter_fields_are_array_query_params(spec, path, fields):
    params = {p["name"]: p for p in spec["paths"][path]["get"].get("parameters", [])}
    for name in fields:
        assert name in params, f"{name} is not a query parameter of GET {path}"
        assert params[name]["in"] == "query"
        schema = params[name]["schema"]
        variants = schema.get("anyOf", [schema])
        assert any(v.get("type") == "array" for v in variants), (name, schema)


def test_no_get_operation_declares_a_request_body(spec):
    offenders = [
        path for path, item in spec["paths"].items() if "requestBody" in item.get("get", {})
    ]
    assert offenders == []
