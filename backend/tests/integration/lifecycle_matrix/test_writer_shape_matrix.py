"""
Every lifecycle writer route against every data shape, over HTTP (_writers.py
lists the writers, _shapes.py the shapes). The writers are the requests of
the lifecycle model's world behind TRIGGER_ACTIONS (state_machine_catalog.py)
and the routes it does not send: reopen, remove, move and edit a line,
correct a delivery, add a line with a demand share, take from stock, fulfil
from stock, auto-allocate, fulfil a demand by hand, cancel a neighbour
demand, edit a lot's quantity, switch and approve a lot's source, assign a
position internally, reverse a completion, split a production order, and
deliveries at the tolerance limits. The shapes are a demand split over two
lines and over two lots with a lower-id neighbour, for the bought, source
and made families, a source demand beside a bought one on one line, a line
moved to another order, a running, a held, a canceled and a completed lot, a
partially delivered line, one with lost pieces, one closed short, a line
under delivery tolerances, the smallest quantity the columns store, a MADE
line beside a bought line with a demand, a lot whose raw material arrived in
part, and a production order on a machine pool. Deliver-all also runs with a
lost rejection, and a provision is recorded.

Every pairing answers no 500, but a success or a documented refusal (409,
422, and 404 where the shape names a row under a parent it left), keeps
every quantity invariant (_invariants.py), leaves the schedule board able to
walk, and leaves every stored status
equal to its derivation, which the drift check after each test confirms. A
pairing whose shape lacks the rows the writer acts on is skipped with that
reason.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration import _lifecycle_seed as seed
from tests.integration.lifecycle_matrix._invariants import assert_quantities_conserved
from tests.integration.lifecycle_matrix._shapes import SHAPES
from tests.integration.lifecycle_matrix._shapes import WEB
from tests.integration.lifecycle_matrix._shapes import build_world
from tests.integration.lifecycle_matrix._shapes import catalogue
from tests.integration.lifecycle_matrix._writers import EVERY_WRITE_PERMISSION
from tests.integration.lifecycle_matrix._writers import WRITERS
from tests.integration.lifecycle_matrix._writers import Writer
from tests.integration.lifecycle_matrix._writers import skip_reason
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("writer", WRITERS, ids=[w.name for w in WRITERS])
async def test_writer_shape_matrix(
    db: AsyncSession, auth_client: Any, create_user: Any, writer: Writer, shape: str
) -> None:
    owner = await create_user(username="owner", email="owner@example.com")
    await catalogue(db, owner)
    client = await auth_client(permissions=EVERY_WRITE_PERMISSION)
    world = await build_world(db, client, owner, shape)
    reason = skip_reason(writer, world)
    if reason is not None:
        pytest.skip(reason)

    response = await writer.call(world)

    allowed = {409, 422, *world.also_refused}
    assert response.status_code < 300 or response.status_code in allowed, (
        response.status_code,
        response.text[:500],
    )
    await assert_quantities_conserved(db)
    # The schedule walks over whatever the writer left, as the board does.
    board = await client.get(
        f"{WEB}/production-schedule/",
        params={"date_from": seed.NOW.date().isoformat(), "date_to": seed.NOW.date().isoformat()},
    )
    assert board.status_code == 200, board.text[:500]
