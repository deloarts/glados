"""
The catalogue tools of the MCP surface over HTTP: a made item by part
number with its revisions and processes, a bought item by part number, an
unknown part number, and the source item and supplier searches.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP],
    )


@pytest.fixture
async def token(db: AsyncSession, agent_owner: User) -> str:
    return await mint_agent_token(db, agent_owner, [Permission.USE_MCP])


async def _made_item(db: AsyncSession, creator_id: int, revision: str) -> MadeItem:
    return await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=NOW,
            changed=NOW,
            changes=["a changelog entry naming its author"],
            archived=False,
            revision=revision,
            revision_date=None,
            revision_note=None,
            article_name=f"Bracket {revision}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number="PN-100",
            material="S235",
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )


async def _milling(db: AsyncSession, creator_id: int) -> FabricationMethod:
    return await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Milling"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )


async def _text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_item_answers_a_made_item_with_revisions_and_processes(
    client: httpx.AsyncClient, db: AsyncSession, agent_owner: User, token: str
) -> None:
    repo = SqlAlchemyMadeItemRepository(db)
    await _made_item(db, agent_owner.id, "A")
    newest = await _made_item(db, agent_owner.id, "B")
    method = await _milling(db, agent_owner.id)
    await repo.save_process(
        MadeItemProcess(
            id=0,
            created=NOW,
            note=None,
            estimated_setup_minutes=15,
            estimated_minutes_per_piece=2.5,
            creator_id=agent_owner.id,
            fabrication_method_id=method.id,
            made_item_id=newest.id,
            position=0,
            group_index=0,
        )
    )
    await db.commit()

    result = await call_tool(client, token, "item", {"part_number": "PN-100"})

    assert result["isError"] is False, await _text(result)
    data = result["structuredContent"]
    assert data["kind"] == "made"
    assert data["item"]["revision"] == "B"
    assert "changes" not in data["item"]
    assert [p["fabrication_method_name"] for p in data["item"]["processes"]] == ["Milling"]
    assert [r["revision"] for r in data["revisions"]] == ["B", "A"]


async def test_item_answers_a_bought_item(
    client: httpx.AsyncClient, db: AsyncSession, agent_owner: User, token: str
) -> None:
    await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            article_name="Round cylinder",
            order_code_1="19210",
            order_code_2=None,
            gtin=None,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number="KT-200",
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=agent_owner.id,
            approver_id=None,
            manufacturer_id=1,
            article_group_ids=[],
            successor_item_id=None,
        )
    )
    await db.commit()

    result = await call_tool(client, token, "item", {"part_number": "KT-200"})

    assert result["isError"] is False, await _text(result)
    assert result["structuredContent"]["kind"] == "bought"
    assert result["structuredContent"]["item"]["article_name"] == "Round cylinder"


async def test_item_names_an_unknown_part_number(client: httpx.AsyncClient, token: str) -> None:
    result = await call_tool(client, token, "item", {"part_number": "NOPE-1"})

    assert result["isError"] is True
    assert "NOPE-1" in await _text(result)


async def test_source_items_finds_a_raw_material_by_dimension(
    client: httpx.AsyncClient, db: AsyncSession, agent_owner: User, token: str
) -> None:
    kind = await SqlAlchemySourceItemTypeRepository(db).save(
        SourceItemType(
            id=0,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Round bar"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=agent_owner.id,
        )
    )
    for dimension in ("D40", "D60"):
        await SqlAlchemySourceItemRepository(db).save(
            SourceItem(
                id=0,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                type_id=kind.id,
                dimension=dimension,
                material="S235",
                mass=None,
                note=None,
                order_code_1=None,
                order_code_2=None,
                status=SourceItemCatalogueStatus.ACTIVE,
                creator_id=agent_owner.id,
                approver_id=None,
                manufacturer_id=None,
                successor_item_id=None,
            )
        )
    await db.commit()

    result = await call_tool(client, token, "source_items", {"search": "D40"})

    assert result["isError"] is False, await _text(result)
    data = result["structuredContent"]
    assert data["total"] == 1
    assert data["items"][0]["dimension"] == "D40"


async def test_suppliers_searches_by_name_and_trims_to_the_limit(
    client: httpx.AsyncClient, auth_client: Any, token: str
) -> None:
    buyer = await auth_client(
        username="buyer", email="buyer@example.com", permissions=[Permission.WRITE_SUPPLIERS]
    )
    for name in ("Festo SE", "Festo Didactic", "Bosch Rexroth"):
        response = await buyer.post(f"{API_WEB}/suppliers/", json={"name": name})
        assert response.status_code == 201, response.text

    result = await call_tool(client, token, "suppliers", {"search": "festo", "limit": 1})

    assert result["isError"] is False, await _text(result)
    data = result["structuredContent"]
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["name"].startswith("Festo")
