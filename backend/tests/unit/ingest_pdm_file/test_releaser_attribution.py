"""
Unit tests for TestPdmReleaserAttribution. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmTransition
from src.modules.platform.domain.entities.user import User
from tests.unit.ingest_pdm_file._helpers import BOUGHT_VARIABLES
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import OBSOLETE_STATE_ID
from tests.unit.ingest_pdm_file._helpers import RELEASED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import UNWATCHED_STATE_ID
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file._helpers import make_user
from tests.unit.ingest_pdm_file.fakes import FakePartNumberRegistry
from tests.unit.ingest_pdm_file.rig import Rig


def make_releaser(*, id: int = 50, username: str = "jdoe") -> User:
    releaser = make_user(id=id, username=username, is_systemuser=False)
    releaser.full_name = "Jane Releaser"
    return releaser


def make_transition(
    *,
    destination_state_id: int = RELEASED_STATE_ID,
    destination_state_name: str = "Released",
    user_id: int = 77,
    user_name: str = "jdoe",
    occurred_at: datetime | None = None,
    comment: str = "release note",
) -> PdmTransition:
    return PdmTransition(
        destination_state_id=destination_state_id,
        destination_state_name=destination_state_name,
        user_id=user_id,
        user_name=user_name,
        occurred_at=occurred_at or datetime(2026, 1, 1, tzinfo=UTC),
        comment=comment,
    )


class TestPdmReleaserAttribution:
    async def test_made_create_attributes_to_resolved_releaser_and_falls_back_revision_fields(self):
        releaser = make_releaser()
        rig = Rig(
            extra_users=[releaser],
            pdm_links={77: releaser.id},
            pdm_transitions=[make_transition(comment="Approved for production")],
        )
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.changed_by_id == releaser.id
        assert item.revision_note == "Approved for production"
        assert item.revision_date == date(2026, 1, 1)
        assert "Jane Releaser" in item.changes[-1]
        # approver_id is untouched (set_approver_from_pdm defaults False).
        assert item.approver_id is None
        assert rig.pdm_gateway.transition_calls == [(100, 5, 1)]

    async def test_revision_date_is_the_tenant_day_of_the_transition(self):
        """23:30 UTC on 31 December is already New Year's Day in Vienna."""
        rig = Rig(
            pdm_transitions=[
                make_transition(occurred_at=datetime(2026, 12, 31, 23, 30, tzinfo=UTC))
            ]
        )
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.revision_date == date(2027, 1, 1)

    async def test_made_create_unresolved_releaser_uses_pdm_username_in_changelog(self):
        rig = Rig(pdm_transitions=[make_transition(user_id=999, user_name="unknown.user")])
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        # No Glados user resolves: changed_by_id keeps the system-actor
        # default, but the changelog names the raw PDM username.
        assert item.changed_by_id == rig.system_user.id
        assert "unknown.user" in item.changes[-1]

    async def test_approver_set_when_toggle_enabled_and_releaser_resolves(self):
        releaser = make_releaser()
        settings = make_pdm_settings()
        settings.set_approver_from_pdm = True
        rig = Rig(
            pdm_settings=settings,
            extra_users=[releaser],
            pdm_links={77: releaser.id},
            pdm_transitions=[make_transition()],
        )
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.approver_id == releaser.id

    async def test_approver_untouched_when_toggle_enabled_but_releaser_unresolved(self):
        settings = make_pdm_settings()
        settings.set_approver_from_pdm = True
        rig = Rig(pdm_settings=settings, pdm_transitions=[make_transition(user_id=999)])
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.approver_id is None

    async def test_transitions_read_failure_is_logged_and_ingest_still_succeeds(self):
        rig = Rig(pdm_transitions_error=PdmApiError("boom", status_code=500, body=""))
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        assert "PDM attribution unavailable" in outcome.message
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.changed_by_id == rig.system_user.id

    async def test_no_matching_transition_leaves_attribution_at_default(self):
        # A transition into an unrelated state must never be picked up.
        rig = Rig(pdm_transitions=[make_transition(destination_state_id=UNWATCHED_STATE_ID)])
        payload = make_payload(kind="made", variables=dict(MADE_VARIABLES))

        outcome = await rig.use_case.execute(payload)

        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.changed_by_id == rig.system_user.id
        assert item.revision_date is None

    async def test_status_transition_reads_the_obsolete_state_list(self):
        releaser = make_releaser()
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(
            made_items=[item],
            extra_users=[releaser],
            pdm_links={77: releaser.id},
            pdm_transitions=[
                make_transition(
                    destination_state_id=OBSOLETE_STATE_ID, destination_state_name="Obsolete"
                )
            ],
        )
        payload = make_payload(
            kind="made",
            state_id=OBSOLETE_STATE_ID,
            state="Obsolete",
            file_version=2,
            variables=dict(MADE_VARIABLES),
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "status"
        updated = await rig.made_item_repo.get_by_id(1)
        assert updated.changed_by_id == releaser.id
        assert "Jane Releaser" in updated.changes[-1]

    async def test_bought_claim_attributes_changelog_to_resolved_releaser(self):
        releaser = make_releaser()
        candidate = make_bought_item(
            1, part_number="OLD-1", data_source=DataSource.WEB, gtin="GTIN-1"
        )
        registry = FakePartNumberRegistry(preclaimed={"OLD-1": "bought"})
        variables = dict(BOUGHT_VARIABLES)
        variables["Glados.Gtin"] = "GTIN-1"
        rig = Rig(
            bought_items=[candidate],
            registry=registry,
            extra_users=[releaser],
            pdm_links={77: releaser.id},
            pdm_transitions=[make_transition()],
        )
        payload = make_payload(kind="bought", file_id=200, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "claimed"
        item = await rig.bought_item_repo.get_by_id(outcome.item_id)
        assert "Jane Releaser" in item.changes[-1]

    async def test_made_update_in_place_never_reads_transitions(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        rig = Rig(made_items=[item], pdm_transitions=[make_transition()])
        variables = dict(MADE_VARIABLES)
        variables["Glados.Mass"] = "999"
        payload = make_payload(kind="made", file_version=2, variables=variables)

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"
        assert rig.pdm_gateway.transition_calls == []
