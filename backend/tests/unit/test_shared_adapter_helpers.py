"""
Coverage for the small helpers the adapters and the request context share:
the UTC re-attach for datetimes read back from SQLite, the case-insensitive
substring match, the current session id, the probe Redis client, the ISO
week start, the gateway cache, the non-blank reason type, the demand bucket
filter and sort, and the upload and download helpers of the file routes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO
from uuid import uuid4

import pytest
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile

from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import bucket_clause
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_secondary_sort,
)
from src.modules.platform.adapters.inbound.api.download_headers import build_download_headers
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.schemas.base import NonBlankReason
from src.modules.platform.adapters.outbound.external._gateway_cache import GatewayCache
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.like_escape import escape_like
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.infrastructure.logging.context import current_session_id
from src.modules.platform.infrastructure.logging.context import session_id_var
from src.modules.platform.infrastructure.redis_client import new_probe_redis_client
from src.shared_kernel.domain.services.clock import start_of_iso_week


class _Base(DeclarativeBase):
    pass


class _Row(_Base):
    __tablename__ = "shared_helper_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    bucket_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due: Mapped[int] = mapped_column(Integer)


def _sql(clause: object) -> str:
    return str(
        clause.compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


class TestUtcAware:
    def test_naive_value_gets_utc_stamped_without_conversion(self) -> None:
        naive = datetime(2026, 3, 1, 12, 30)

        result = utc_aware(naive)

        assert result == datetime(2026, 3, 1, 12, 30, tzinfo=UTC)

    def test_aware_value_is_returned_unchanged(self) -> None:
        aware = datetime(2026, 3, 1, 12, 30, tzinfo=timezone(timedelta(hours=2)))

        assert utc_aware(aware) is aware

    def test_none_stays_none(self) -> None:
        assert utc_aware(None) is None


class TestContainsCi:
    def test_matches_the_hand_written_escaped_ilike(self) -> None:
        term = "50%_a\\b"
        expected = _Row.name.ilike(f"%{escape_like(term)}%", escape="\\")

        assert _sql(contains_ci(_Row.name, term)) == _sql(expected)


class TestCurrentSessionId:
    def test_parses_the_session_var(self) -> None:
        sid = uuid4()
        token = session_id_var.set(str(sid))
        try:
            assert current_session_id() == sid
        finally:
            session_id_var.reset(token)

    def test_none_without_a_session(self) -> None:
        token = session_id_var.set(None)
        try:
            assert current_session_id() is None
        finally:
            session_id_var.reset(token)

    def test_none_for_a_malformed_value(self) -> None:
        token = session_id_var.set("not-a-uuid")
        try:
            assert current_session_id() is None
        finally:
            session_id_var.reset(token)


class TestNewProbeRedisClient:
    def test_carries_the_one_second_timeouts_and_is_never_shared(self) -> None:
        first = new_probe_redis_client()
        second = new_probe_redis_client()

        kwargs = first.connection_pool.connection_kwargs
        assert kwargs["socket_connect_timeout"] == 1
        assert kwargs["socket_timeout"] == 1
        assert first is not second


class TestStartOfIsoWeek:
    def test_monday_is_its_own_week_start(self) -> None:
        assert start_of_iso_week(date(2026, 10, 19)) == date(2026, 10, 19)

    def test_sunday_maps_back_to_monday(self) -> None:
        assert start_of_iso_week(date(2026, 10, 25)) == date(2026, 10, 19)

    def test_week_crossing_the_year_boundary(self) -> None:
        assert start_of_iso_week(date(2027, 1, 1)) == date(2026, 12, 28)


class _FakeGateway:
    def __init__(self, key: str) -> None:
        self.key = key
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class TestGatewayCache:
    def test_reuses_the_gateway_per_key(self) -> None:
        cache: GatewayCache[str, _FakeGateway] = GatewayCache(_FakeGateway, 2)

        assert cache.get("a") is cache.get("a")
        assert cache.get("a") is not cache.get("b")

    def test_evicts_the_least_recently_used_gateway(self) -> None:
        cache: GatewayCache[str, _FakeGateway] = GatewayCache(_FakeGateway, 2)
        first = cache.get("a")
        cache.get("b")
        cache.get("a")
        cache.get("c")

        assert len(cache) == 2
        assert cache.get("a") is first
        assert not first.closed

    async def test_aclose_all_closes_and_empties(self) -> None:
        cache: GatewayCache[str, _FakeGateway] = GatewayCache(_FakeGateway, 2)
        gateway = cache.get("a")

        await cache.aclose_all()

        assert gateway.closed
        assert len(cache) == 0

    def test_clear_empties_without_closing(self) -> None:
        cache: GatewayCache[str, _FakeGateway] = GatewayCache(_FakeGateway, 2)
        gateway = cache.get("a")

        cache.clear()

        assert len(cache) == 0
        assert not gateway.closed


class _ReasonRequest(BaseModel):
    reason: NonBlankReason = Field(..., min_length=1, max_length=10)


class TestNonBlankReason:
    def test_trims_the_reason(self) -> None:
        assert _ReasonRequest(reason="  late ").reason == "late"

    def test_whitespace_only_is_refused_with_the_blank_message(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _ReasonRequest(reason="   ")

        assert "reason must not be blank." in str(exc.value)

    def test_length_limits_stay_on_the_field(self) -> None:
        with pytest.raises(ValidationError):
            _ReasonRequest(reason="x" * 11)


class TestBucketClause:
    def test_combines_ids_and_unbucketed(self) -> None:
        clause = bucket_clause(_Row.bucket_id, [1, 2], True)

        sql = _sql(clause)
        assert "bucket_id IN (1, 2)" in sql
        assert "bucket_id IS NULL" in sql

    def test_ids_only(self) -> None:
        sql = _sql(bucket_clause(_Row.bucket_id, [3], None))

        assert "IS NULL" not in sql


_SORT_COLUMNS = {"name": _Row.name, "bucket_name": _Row.name}


class TestDemandSecondarySort:
    def test_unknown_column_falls_back_to_the_default_descending(self) -> None:
        sql = _sql(demand_secondary_sort("nope", "asc", _SORT_COLUMNS, _Row.due))

        assert sql == "shared_helper_rows.due DESC"

    def test_requested_column_and_direction(self) -> None:
        sql = _sql(demand_secondary_sort("name", "desc", _SORT_COLUMNS, _Row.due))

        assert sql == "shared_helper_rows.name DESC"

    def test_bucket_name_sorts_nulls_last(self) -> None:
        sql = _sql(demand_secondary_sort("bucket_name", "asc", _SORT_COLUMNS, _Row.due))

        assert sql == "shared_helper_rows.name ASC NULLS LAST"


class TestReadUpload:
    async def test_reads_bytes_name_and_type(self) -> None:
        upload = UploadFile(
            BytesIO(b"abc"),
            filename="a.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )

        assert await read_upload(upload) == (b"abc", "a.pdf", "application/pdf")

    async def test_falls_back_to_upload_and_octet_stream(self) -> None:
        upload = UploadFile(BytesIO(b"x"))

        assert await read_upload(upload) == (b"x", "upload", "application/octet-stream")


class TestFileDownloadResponse:
    def test_serves_the_bytes_with_the_download_headers(self) -> None:
        response = file_download_response(
            b"png", "pic.png", content_type="image/png", disposition="inline"
        )

        assert response.body == b"png"
        assert response.media_type == "image/png"
        expected = build_download_headers("pic.png", content_type="image/png", disposition="inline")
        for name, value in expected.items():
            assert response.headers[name] == value
