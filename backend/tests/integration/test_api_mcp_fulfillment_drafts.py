"""
The draft tools of Planning and fulfillment over the MCP surface: each one
creates a DRAFT purchase order, quote request or production lot for open
demands through the web app's own create use cases, records the token owner
as the changer, logs the created records, answers a repeated idempotency key
with the first call's records, and is seen only by a personal access token
carrying the write permission it needs.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import replace
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import ADMIN_SETTINGS_SEEDS
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestSupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import list_tool_names
from tests.integration._mcp_helpers import logged_calls
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration._mcp_helpers import seed_security
from tests.integration.repository_reads._graph import Graph

DRAFT_TOOLS = {"draft_purchase_order", "draft_quote_request", "draft_production_lot"}
DRAFTING = [Permission.USE_MCP, Permission.WRITE_ORDERS, Permission.WRITE_LOTS]


@pytest.fixture(autouse=True)
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture(autouse=True)
async def production_settings(db: AsyncSession) -> None:
    """The production settings a new lot reads, as InitDatabase seeds them,
    which the integration schema does not."""
    seed = next(s for s in ADMIN_SETTINGS_SEEDS if s.label == "production")
    await seed.save(SqlAlchemyAdminSettingsRepository(db))(seed.build())
    await db.commit()


@pytest.fixture
async def owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[
            Permission.WRITE_PAT,
            Permission.MANAGE_API_KEYS,
            *DRAFTING,
        ],
    )


@pytest.fixture
async def graph(db: AsyncSession, create_user: Callable[..., Awaitable[User]]) -> Graph:
    creator = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, creator, other)


@pytest.fixture
async def token(db: AsyncSession, owner: User) -> str:
    return await mint_agent_token(db, owner, DRAFTING)


async def _bought_demand(graph: Graph, quantity: float, **values: Any) -> int:
    template = await graph.bought_demand()
    saved = await SqlAlchemyBoughtItemDemandItemRepository(graph.db).save(
        replace(
            template,
            id=0,
            quantity=quantity,
            status=values.pop("status", BoughtItemDemandStatus.OPEN),
            changes=[],
            **values,
        )
    )
    await graph.db.commit()
    return saved.id


async def _made_demand(graph: Graph, quantity: float) -> int:
    template = await graph.made_demand()
    saved = await SqlAlchemyMadeItemDemandItemRepository(graph.db).save(
        replace(template, id=0, quantity=quantity, status=MadeItemDemandStatus.OPEN, changes=[])
    )
    await graph.db.commit()
    return saved.id


async def _row[M: Base](db: AsyncSession, model: type[M], public_id: str) -> M:
    db.expire_all()
    return (await db.execute(select(model).where(model.public_id == UUID(public_id)))).scalar_one()


async def _count(db: AsyncSession, model: type[Base]) -> int:
    db.expire_all()
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


def _data(result: dict[str, Any]) -> dict[str, Any]:
    assert result["isError"] is False, result["content"][0]["text"]
    data: dict[str, Any] = result["structuredContent"]
    return data


# ── draft_purchase_order ──────────────────────────────────────────────


async def test_draft_purchase_order_creates_a_draft_with_one_line_per_item(
    client: httpx.AsyncClient, db: AsyncSession, graph: Graph, owner: User, token: str
) -> None:
    first = await _bought_demand(graph, 5.0)
    second = await _bought_demand(graph, 3.0)
    material = await graph.source_demand()
    supplier = await graph.supplier()

    data = _data(
        await call_tool(
            client,
            token,
            "draft_purchase_order",
            {
                "supplier_id": supplier.id,
                "bought_demand_ids": [first, second],
                "source_demand_ids": [material.id],
                "note": "Drafted by an agent",
            },
        )
    )

    assert data["complete"] is True
    order = await _row(db, OrderOrmModel, data["order"]["public_id"])
    assert order.status == OrderStatus.DRAFT
    assert order.ordered_date is None
    assert order.changed_by_id == owner.id
    assert order.supplier_id == supplier.id
    order_id, order_ref = order.id, f"order:{order.public_id}"
    lines = data["order"]["lines"]
    assert [(line["quantity"], line["demand_ids"]) for line in lines] == [
        (8.0, [first, second]),
        (material.quantity, [material.id]),
    ]
    for line in lines:
        item = await _row(db, OrderItemOrmModel, line["public_id"])
        assert (item.order_id, item.status, item.changed_by_id) == (order_id, "pending", owner.id)
    [call] = await logged_calls(db)
    assert (call.tool, call.outcome) == ("draft_purchase_order", "ok")
    assert call.created_refs == [
        order_ref,
        *(f"order_item:{line['public_id']}" for line in lines),
    ]


async def test_draft_purchase_order_refuses_a_canceled_demand_before_writing(
    client: httpx.AsyncClient, db: AsyncSession, graph: Graph, token: str
) -> None:
    demand = await _bought_demand(
        graph, 5.0, status=BoughtItemDemandStatus.CANCELED, canceled_at=now_utc()
    )
    supplier = await graph.supplier()
    before = await _count(db, OrderOrmModel)

    result = await call_tool(
        client,
        token,
        "draft_purchase_order",
        {"supplier_id": supplier.id, "bought_demand_ids": [demand]},
    )

    assert result["isError"] is True
    assert "canceled" in result["content"][0]["text"]
    assert await _count(db, OrderOrmModel) == before
    [call] = await logged_calls(db)
    assert (call.outcome, call.created_refs) == ("error", [])


async def test_draft_purchase_order_keeps_the_lines_before_a_refused_one(
    client: httpx.AsyncClient, db: AsyncSession, graph: Graph, token: str
) -> None:
    whole = await _bought_demand(graph, 2.0)
    # A set counts whole things, so the use case refuses a line of 1.5.
    fractional = await _bought_demand(graph, 1.5, unit="set")
    supplier = await graph.supplier()

    data = _data(
        await call_tool(
            client,
            token,
            "draft_purchase_order",
            {"supplier_id": supplier.id, "bought_demand_ids": [whole, fractional]},
        )
    )

    assert data["complete"] is False
    assert f"[{fractional}]" in data["error"]
    [line] = data["order"]["lines"]
    assert line["demand_ids"] == [whole]
    order = await _row(db, OrderOrmModel, data["order"]["public_id"])
    assert order.status == OrderStatus.DRAFT
    order_ref = f"order:{order.public_id}"
    [call] = await logged_calls(db)
    assert call.created_refs == [order_ref, f"order_item:{line['public_id']}"]


# ── draft_quote_request ───────────────────────────────────────────────


async def test_draft_quote_request_creates_a_draft_that_is_not_sent(
    client: httpx.AsyncClient, db: AsyncSession, graph: Graph, owner: User, token: str
) -> None:
    demand = await _bought_demand(graph, 4.0)
    supplier = await graph.supplier()

    data = _data(
        await call_tool(
            client,
            token,
            "draft_quote_request",
            {"supplier_ids": [supplier.id], "bought_demand_ids": [demand]},
        )
    )

    request = await _row(db, QuoteRequestOrmModel, data["quote_request"]["public_id"])
    assert request.status == QuoteRequestStatus.DRAFT
    assert request.changed_by_id == owner.id
    [row] = (
        (
            await db.execute(
                select(QuoteRequestSupplierOrmModel).where(
                    QuoteRequestSupplierOrmModel.quote_request_id == request.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert (row.supplier_id, row.sent_at) == (supplier.id, None)
    assert [line["quantity"] for line in data["quote_request"]["lines"]] == [4.0]
    [call] = await logged_calls(db)
    assert call.created_refs == [f"quote_request:{data['quote_request']['public_id']}"]


# ── draft_production_lot ──────────────────────────────────────────────


async def test_draft_production_lot_creates_a_draft_lot_for_the_demands(
    client: httpx.AsyncClient, db: AsyncSession, graph: Graph, owner: User, token: str
) -> None:
    first = await _made_demand(graph, 2.0)
    second = await _made_demand(graph, 3.0)

    data = _data(
        await call_tool(client, token, "draft_production_lot", {"made_demand_ids": [first, second]})
    )

    lot = await _row(db, ProductionLotOrmModel, data["lot"]["public_id"])
    assert lot.status == LotStatus.DRAFT
    assert "note" not in data
    assert (lot.quantity, lot.changed_by_id) == (5.0, owner.id)
    assert data["lot"]["demand_ids"] == [first, second]
    [call] = await logged_calls(db)
    assert call.created_refs == [f"lot:{data['lot']['public_id']}"]


# ── Every draft tool ──────────────────────────────────────────────────


async def _order_args(graph: Graph) -> dict[str, Any]:
    return {
        "supplier_id": (await graph.supplier()).id,
        "bought_demand_ids": [await _bought_demand(graph, 2.0)],
    }


async def _quote_args(graph: Graph) -> dict[str, Any]:
    return {
        "supplier_ids": [(await graph.supplier()).id],
        "bought_demand_ids": [await _bought_demand(graph, 2.0)],
    }


async def _lot_args(graph: Graph) -> dict[str, Any]:
    return {"made_demand_ids": [await _made_demand(graph, 2.0)]}


@pytest.mark.parametrize(
    ("tool", "arrange", "model"),
    [
        ("draft_purchase_order", _order_args, OrderOrmModel),
        ("draft_quote_request", _quote_args, QuoteRequestOrmModel),
        ("draft_production_lot", _lot_args, ProductionLotOrmModel),
    ],
)
async def test_a_repeated_idempotency_key_creates_no_second_draft(
    client: httpx.AsyncClient,
    db: AsyncSession,
    graph: Graph,
    token: str,
    tool: str,
    arrange: Callable[[Graph], Awaitable[dict[str, Any]]],
    model: type[Base],
) -> None:
    arguments = {**await arrange(graph), "idempotency_key": "plan-42"}
    before = await _count(db, model)

    first = _data(await call_tool(client, token, tool, arguments))
    again = _data(await call_tool(client, token, tool, arguments))

    assert await _count(db, model) == before + 1
    first_call, second_call = await logged_calls(db)
    assert again == {"replayed": True, "created": first_call.created_refs}
    assert second_call.created_refs == first_call.created_refs
    assert first.get("replayed") is None


async def test_a_token_sees_only_the_drafts_its_permissions_allow(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    read_only = await mint_agent_token(db, owner, [Permission.USE_MCP], name="read")
    orders_only = await mint_agent_token(
        db, owner, [Permission.USE_MCP, Permission.WRITE_ORDERS], name="orders"
    )

    assert DRAFT_TOOLS.isdisjoint(await list_tool_names(client, read_only))
    assert DRAFT_TOOLS & set(await list_tool_names(client, orders_only)) == {
        "draft_purchase_order",
        "draft_quote_request",
    }
    refused = await call_tool(client, orders_only, "draft_production_lot", {"made_demand_ids": [1]})
    assert refused["isError"] is True


async def test_an_api_key_sees_no_draft_tool(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await seed_security(db, enable_api_key_auth=True)
    created = await CreateApiKey(
        SqlAlchemyApiKeyRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemyUnitOfWork(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        hash_password_fn=aget_hash,
    ).execute(
        actor=owner,
        cmd=CreateApiKeyCommand(name="unattended", permissions=DRAFTING, expires_in_days=7),
    )

    names = await list_tool_names(client, created.key)

    assert names
    assert DRAFT_TOOLS.isdisjoint(names)
    refused = await call_tool(client, created.key, "draft_production_lot", {"made_demand_ids": [1]})
    assert refused["isError"] is True


# ── provenance for the web app ────────────────────────────────────────


async def test_every_user_can_see_which_records_an_agent_created(
    client: httpx.AsyncClient,
    db: AsyncSession,
    graph: Graph,
    owner: User,
    token: str,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    demand = await _bought_demand(graph, 5.0)
    supplier = await graph.supplier()
    data = _data(
        await call_tool(
            client,
            token,
            "draft_purchase_order",
            {"supplier_id": supplier.id, "bought_demand_ids": [demand]},
        )
    )
    order_ref = f"order:{data['order']['public_id']}"
    unrelated = "order:00000000-0000-0000-0000-000000000000"
    colleague = await auth_client(username="colleague", email="colleague@example.com")

    found = await colleague.post(
        "/api/v1/web/agent-calls/created-records",
        json={"refs": [order_ref, unrelated, order_ref]},
        headers={"X-Requested-With": "glados"},
    )
    logged = await auth_client(
        [Permission.READ_SETTINGS], username="admin", email="admin@example.com"
    )
    by_ref = await logged.get("/api/v1/web/agent-calls/", params={"created_ref": order_ref})

    assert found.status_code == 200, found.text
    [record] = found.json()
    assert (record["ref"], record["token_name"], record["user_id"]) == (
        order_ref,
        "agent",
        owner.id,
    )
    assert by_ref.json()["total"] == 1
    assert by_ref.json()["items"][0]["tool"] == "draft_purchase_order"


async def test_the_created_records_lookup_takes_at_most_one_page(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    user = await auth_client(username="colleague", email="colleague@example.com")

    response = await user.post(
        "/api/v1/web/agent-calls/created-records",
        json={"refs": [f"order:{i}" for i in range(201)]},
        headers={"X-Requested-With": "glados"},
    )

    assert response.status_code == 422
