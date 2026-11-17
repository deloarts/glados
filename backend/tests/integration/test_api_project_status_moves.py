"""
A project's status moves through its intent table: holding, resuming,
completing, archiving and reopening need manage:projects, a client sends the
edit version it read, and completing or archiving is refused while the
project still has live work, counted like a delete. Holding is allowed with
open work, since it only stops new work. The web read offers the moves the
reading user may take and the counts that block the others.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.project_work_repository import (
    SqlAlchemyProjectWork,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from tests.integration.conftest import _new_client
from tests.integration.conftest import auth_headers
from tests.integration.test_api_project_delete_guard import MANAGER
from tests.integration.test_api_project_delete_guard import PROJECTS
from tests.integration.test_api_project_delete_guard import _add
from tests.integration.test_api_project_delete_guard import _bought_demand
from tests.integration.test_api_project_delete_guard import _line
from tests.integration.test_api_project_delete_guard import _order
from tests.integration.test_api_project_delete_guard import _project

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def _body(project: dict, **changes: object) -> dict:
    """The PUT body of `project` with `changes` applied."""
    return {
        "project_number": project["project_number"],
        "description": project["description"],
        "status": project["status"],
        "expected_edit_version": project["edit_version"],
        **changes,
    }


async def _read(client, project_id: int) -> dict:
    resp = await client.get(f"{PROJECTS}/{project_id}")
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


async def _move(client, project_id: int, status: str):
    project = await _read(client, project_id)
    return await client.put(f"{PROJECTS}/{project_id}", json=_body(project, status=status))


async def test_completing_or_archiving_with_live_work_answers_409_with_the_counts(
    auth_client, db: AsyncSession
) -> None:
    project = await _project(db, "P-LIVE")
    await _add(db, _bought_demand(project.id, status="open"))
    await db.commit()
    client = await auth_client(permissions=MANAGER)

    read = await _read(client, project.id)
    assert read["actions"] == ["hold"]
    assert read["live_work"]["bought_demands"] == 1

    for target in ("completed", "archived"):
        resp = await _move(client, project.id, target)
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "ProjectStatusMoveBlockedError"
        assert "1 bought item demand" in resp.json()["detail"]
    assert (await _read(client, project.id))["status"] == "active"


async def test_holding_is_allowed_with_open_work_and_resuming_brings_it_back(
    auth_client, db: AsyncSession
) -> None:
    project = await _project(db, "P-HOLD")
    await _add(db, _bought_demand(project.id, status="open"))
    await db.commit()
    client = await auth_client(permissions=MANAGER)

    held = await _move(client, project.id, "on_hold")
    assert held.status_code == 200, held.text
    assert held.json()["status"] == "on_hold"
    assert "resume" in held.json()["actions"]

    resumed = await _move(client, project.id, "active")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "active"


async def test_a_project_without_live_work_completes_archives_and_reopens(
    auth_client, db: AsyncSession
) -> None:
    project = await _project(db, "P-EMPTY")
    client = await auth_client(permissions=MANAGER)
    assert {"hold", "complete", "archive", "remove"} <= set(
        (await _read(client, project.id))["actions"]
    )

    for target in ("completed", "archived", "active"):
        resp = await _move(client, project.id, target)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == target


async def test_an_open_quote_request_line_on_the_project_counts_as_live_work(
    auth_client, db: AsyncSession
) -> None:
    project = await _project(db, "P-RFQ")
    request = await _add(
        db,
        QuoteRequestOrmModel(request_number="RFQ-1", created=NOW, status="draft", creator_id=1),
    )
    await _add(
        db,
        QuoteRequestLineOrmModel(
            quote_request_id=request.id,
            position=1,
            line_type="VIRTUAL",
            virtual_name="Bracket",
            quantity=1.0,
            unit="pcs",
            created=NOW,
            project_id=project.id,
        ),
    )
    await db.commit()

    work = await SqlAlchemyProjectWork(db).get_live_work(project.id)
    assert work == ProjectLiveWork(quote_requests=1)

    client = await auth_client(permissions=MANAGER)
    resp = await _move(client, project.id, "archived")
    assert resp.status_code == 409, resp.text
    assert "1 open quote request" in resp.json()["detail"]


@pytest.mark.parametrize("order_line", ["canceled", "removed"])
async def test_a_line_whose_award_was_voided_counts_as_an_open_quote_request_line(
    auth_client, db: AsyncSession, order_line: str
) -> None:
    """The line was awarded, but the order line of the award was canceled or
    removed, so the line is open again and the request is a draft again."""
    project = await _project(db, f"P-VOID-{order_line}")
    request = await _add(
        db,
        QuoteRequestOrmModel(request_number="RFQ-1", created=NOW, status="draft", creator_id=1),
    )
    line = await _add(
        db,
        QuoteRequestLineOrmModel(
            quote_request_id=request.id,
            position=1,
            line_type="VIRTUAL",
            virtual_name="Bracket",
            quantity=1.0,
            unit="pcs",
            created=NOW,
            project_id=project.id,
            awarded_at=NOW,
        ),
    )
    if order_line == "canceled":
        order = await _order(db, "BN-1", "canceled")
        await _line(
            db,
            order.id,
            project.id,
            status="canceled",
            canceled_at=NOW,
            quote_request_line_id=line.id,
        )
    await db.commit()

    work = await SqlAlchemyProjectWork(db).get_live_work(project.id)
    assert work == ProjectLiveWork(quote_requests=1)

    client = await auth_client(permissions=MANAGER)
    resp = await _move(client, project.id, "completed")
    assert resp.status_code == 409, resp.text
    assert "1 open quote request" in resp.json()["detail"]


async def test_a_stale_edit_version_answers_409(auth_client, db: AsyncSession) -> None:
    project = await _project(db, "P-STALE")
    client = await auth_client(permissions=MANAGER)
    stale = await _read(client, project.id)

    first = await client.put(
        f"{PROJECTS}/{project.id}", json=_body(stale, description="First edit")
    )
    assert first.status_code == 200, first.text
    assert first.json()["edit_version"] == stale["edit_version"] + 1

    second = await client.put(f"{PROJECTS}/{project.id}", json=_body(stale, status="on_hold"))
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "ConcurrentModificationError"
    assert (await _read(client, project.id))["status"] == "active"


async def test_the_designated_user_edits_the_project_but_not_its_status(
    create_user, db: AsyncSession
) -> None:
    owner = await create_user(permissions=["write:projects"])
    project = await _project(db, "P-OWNED")
    project.designated_user_id = owner.id
    await SqlAlchemyProjectRepository(db).save(project)
    await db.commit()
    client = _new_client()
    client.headers.update(await auth_headers(owner))
    try:
        read = await _read(client, project.id)
        # Offered, so the button can show disabled with the missing permission.
        assert "hold" in read["actions"]

        edited = await client.put(
            f"{PROJECTS}/{project.id}", json=_body(read, description="Owner edit")
        )
        assert edited.status_code == 200, edited.text

        moved = await _move(client, project.id, "on_hold")
        assert moved.status_code == 403, moved.text
        assert (await _read(client, project.id))["status"] == "active"
    finally:
        await client.aclose()
