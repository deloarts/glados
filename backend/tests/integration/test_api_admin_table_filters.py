"""
Row filters of the admin tables that are paged on the server: the settings
audit log, the PDM sync runs and their entries, the PDM reconciliation
findings, one webhook subscription's deliveries, and the personal access
token and API key lists. Each parameter gets one request that keeps the
matching row and drops the other, so a filter that is silently ignored
fails here.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy import update

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_reconciliation_finding_repository import (
    SqlAlchemyPdmReconciliationFindingRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
    PdmReconciliationFinding,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.platform.adapters.outbound.persistence.models.api_key_model import ApiKeyOrmModel
from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatOrmModel
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import TEST_PASSWORD

# Late on 1 September in Vienna, the tenant's timezone the day filters read
# (23:30 CEST).
_DAY_1 = datetime(2026, 9, 1, 21, 30, tzinfo=UTC)
_DAY_3 = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


def _ids(body: dict) -> set[int]:
    return {row["id"] for row in body["items"]}


# ── Settings audit ─────────────────────────────────────────────────────


AUDIT = "/api/v1/web/admin/settings/audit"


@pytest.fixture
async def audit_rows(db) -> tuple[int, int]:
    repo = SqlAlchemyAdminSettingsRepository(db)
    first = await repo.append_audit(
        AdminSettingsAuditEntry(
            id=0,
            changed_at=_DAY_1,
            changed_by_id=None,
            changed_by_username="alice.admin",
            settings_domain="mail",
            summary="SMTP host changed",
        )
    )
    await db.commit()
    second = await repo.append_audit(
        AdminSettingsAuditEntry(
            id=0,
            changed_at=_DAY_3,
            changed_by_id=None,
            changed_by_username="bob",
            settings_domain="security",
            summary="Session timeout raised",
        )
    )
    await db.commit()
    return first.id, second.id


class TestSettingsAuditFilters:
    @pytest.mark.parametrize(
        ("params", "keep_first"),
        [
            ({"changed_by": "ALICE"}, True),
            ({"changed_by": "bob"}, False),
            ({"summary": "smtp"}, True),
            ({"summary": "timeout"}, False),
            ({"changed_from": "2026-09-02"}, False),
            ({"changed_to": "2026-09-01"}, True),
        ],
    )
    async def test_filter_keeps_only_the_matching_row(
        self, auth_client, audit_rows, params, keep_first
    ):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(AUDIT, params=params)).json()

        expected = audit_rows[0] if keep_first else audit_rows[1]
        assert _ids(body) == {expected}
        assert body["total"] == 1

    async def test_date_range_is_inclusive_of_both_days(self, auth_client, audit_rows):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (
            await client.get(
                AUDIT, params={"changed_from": "2026-09-01", "changed_to": "2026-09-03"}
            )
        ).json()

        assert _ids(body) == set(audit_rows)

    async def test_like_wildcards_match_literally(self, auth_client, audit_rows):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        assert (await client.get(AUDIT, params={"summary": "%"})).json()["total"] == 0

    async def test_changed_by_id_matches_the_changing_user_exactly(self, auth_client, db):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        me = (await client.get("/api/v1/web/users/me")).json()["id"]
        repo = SqlAlchemyAdminSettingsRepository(db)
        mine = await repo.append_audit(
            AdminSettingsAuditEntry(
                id=0,
                changed_at=_DAY_1,
                changed_by_id=me,
                changed_by_username="tester",
                settings_domain="mail",
                summary="SMTP host changed",
            )
        )
        await repo.append_audit(
            AdminSettingsAuditEntry(
                id=0,
                changed_at=_DAY_3,
                changed_by_id=None,
                changed_by_username="tester2",
                settings_domain="mail",
                summary="SMTP port changed",
            )
        )
        await db.commit()

        assert _ids((await client.get(AUDIT, params={"changed_by_id": me})).json()) == {mine.id}
        assert (await client.get(AUDIT, params={"changed_by_id": me + 999})).json()["total"] == 0


# ── PDM sync runs and entries ──────────────────────────────────────────


RUNS = "/api/v1/web/admin/settings/pdm/runs"


async def _run(
    db, *, started_at: datetime, trigger: PdmSyncTrigger, error: str | None
) -> PdmSyncRun:
    return await SqlAlchemyPdmSyncRunRepository(db).start(
        PdmSyncRun(
            id=0,
            started_at=started_at,
            finished_at=started_at + timedelta(seconds=5),
            trigger=trigger,
            files_seen=0,
            changed=0,
            ingested=0,
            skipped=0,
            conflicts=0,
            errors=0,
            missing=0,
            error=error,
            summary=None,
            folders_walked=0,
        )
    )


@pytest.fixture
async def runs(db) -> tuple[int, int]:
    first = await _run(
        db, started_at=_DAY_1, trigger=PdmSyncTrigger.SCHEDULED, error="Vault login refused"
    )
    second = await _run(db, started_at=_DAY_3, trigger=PdmSyncTrigger.MANUAL, error=None)
    return first.id, second.id


class TestPdmSyncRunFilters:
    @pytest.mark.parametrize(
        ("params", "keep_first"),
        [
            ({"trigger": ["scheduled"]}, True),
            ({"trigger": ["manual", "retry"]}, False),
            ({"started_from": "2026-09-02"}, False),
            ({"started_to": "2026-09-01"}, True),
            ({"error": "LOGIN"}, True),
        ],
    )
    async def test_filter_keeps_only_the_matching_run(self, auth_client, runs, params, keep_first):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(RUNS, params=params)).json()

        expected = runs[0] if keep_first else runs[1]
        assert _ids(body) == {expected}
        assert body["total"] == 1

    async def test_both_triggers_keep_both_runs(self, auth_client, runs):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(RUNS, params={"trigger": ["scheduled", "manual"]})).json()

        assert _ids(body) == set(runs)


@pytest.fixture
async def run_with_entries(db) -> tuple[int, int, int]:
    repo = SqlAlchemyPdmSyncRunRepository(db)
    run = await _run(db, started_at=_DAY_1, trigger=PdmSyncTrigger.SCHEDULED, error=None)

    def entry(file_id: int, name: str, path: str, kind: str) -> PdmSyncRunEntry:
        return PdmSyncRunEntry(
            id=0,
            run_id=run.id,
            vault_id="V1",
            file_id=file_id,
            name=name,
            path=path,
            kind=kind,
            action="created",
            item_id=None,
            message="ok",
            created_at=_DAY_1,
        )

    await repo.add_entries(
        run.id,
        [
            entry(1, "Bracket.SLDPRT", "\\Parts\\Bracket.SLDPRT", "made"),
            entry(2, "Screw.SLDPRT", "\\Purchased\\Screw.SLDPRT", "bought"),
        ],
    )
    await db.commit()
    return run.id, 1, 2


class TestPdmSyncRunEntryFilters:
    @pytest.mark.parametrize(
        ("params", "keep_file"),
        [
            ({"search": "bracket"}, 1),
            ({"search": "purchased"}, 2),
            ({"kind": "made"}, 1),
            ({"kind": "bought"}, 2),
        ],
    )
    async def test_filter_keeps_only_the_matching_entry(
        self, auth_client, run_with_entries, params, keep_file
    ):
        run_id = run_with_entries[0]
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(f"{RUNS}/{run_id}/entries", params=params)).json()

        assert body["total"] == 1
        assert body["items"][0]["file_id"] == keep_file


# ── PDM reconciliation findings ─────────────────────────────────────────


FINDINGS = "/api/v1/web/admin/settings/pdm/reconciliation/findings"


@pytest.fixture
async def findings(db) -> None:
    run = await _run(db, started_at=_DAY_1, trigger=PdmSyncTrigger.RECONCILIATION, error=None)

    def finding(file_id: int, part_number: str, message: str) -> PdmReconciliationFinding:
        return PdmReconciliationFinding(
            id=0,
            run_id=run.id,
            category=PdmReconciliationCategory.REVISION_LAG,
            severity=PdmReconciliationSeverity.WARNING,
            kind="made",
            item_id=None,
            file_id=file_id,
            part_number=part_number,
            revision="A",
            message=message,
            count=1,
            created_at=_DAY_1,
        )

    await SqlAlchemyPdmReconciliationFindingRepository(db).add_many(
        [
            finding(1, "PUR-26-00001", "Revision behind the vault"),
            finding(2, "MFG-26-00002", "Mentions PUR in the text only"),
        ]
    )
    await db.commit()


class TestPdmReconciliationFindingFilters:
    @pytest.mark.parametrize(
        ("params", "keep_file"),
        [
            ({"part_number": "pur-26"}, 1),
            ({"part_number": "MFG"}, 2),
            ({"message": "behind"}, 1),
            ({"message": "text only"}, 2),
        ],
    )
    async def test_filter_keeps_only_the_matching_finding(
        self, auth_client, findings, params, keep_file
    ):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(FINDINGS, params=params)).json()

        assert body["total"] == 1
        assert body["items"][0]["file_id"] == keep_file


# ── Webhook deliveries ─────────────────────────────────────────────────


@pytest.fixture
async def reader(auth_client) -> httpx.AsyncClient:
    return await auth_client(permissions=[Permission.READ_SETTINGS])


@pytest.fixture
async def deliveries(db, reader) -> tuple[int, int, int]:
    creator = await db.scalar(select(UserOrmModel).limit(1))
    subscription = await SqlAlchemyWebhookSubscriptionRepository(db).save(
        WebhookSubscription(
            id=0,
            name="Hook",
            url="https://example.com/hook",
            secret="s3cret",
            event_types=["*"],
            is_active=True,
            created=_DAY_1,
            creator_id=creator.id,
        )
    )
    repo = SqlAlchemyWebhookDeliveryRepository(db)

    async def delivery(event_type: str, attempted_at: datetime, success: bool) -> WebhookDelivery:
        return await repo.save(
            WebhookDelivery(
                id=0,
                subscription_id=subscription.id,
                event_type=event_type,
                source_event_id=f"{event_type}-{attempted_at.isoformat()}",
                payload="{}",
                attempted_at=attempted_at,
                http_status=200 if success else 500,
                duration_ms=10,
                error=None if success else "HTTP 500",
                success=success,
            )
        )

    first = await delivery("lot.created", _DAY_1, True)
    second = await delivery("order.updated", _DAY_3, False)
    await db.commit()
    return subscription.id, first.id, second.id


class TestWebhookDeliveryFilters:
    @pytest.mark.parametrize(
        ("params", "keep_first"),
        [
            ({"success": "true"}, True),
            ({"success": "false"}, False),
            ({"event_type": "lot.created"}, True),
            ({"event_type": "order.updated"}, False),
            ({"attempted_from": "2026-09-02"}, False),
            ({"attempted_to": "2026-09-01"}, True),
        ],
    )
    async def test_filter_keeps_only_the_matching_delivery(
        self, reader, deliveries, params, keep_first
    ):
        subscription_id, first_id, second_id = deliveries

        body = (
            await reader.get(
                f"/api/v1/web/admin/webhooks/{subscription_id}/deliveries", params=params
            )
        ).json()

        assert _ids(body) == {first_id if keep_first else second_id}
        assert body["total"] == 1

    async def test_event_type_is_an_exact_match(self, reader, deliveries):
        subscription_id = deliveries[0]

        body = (
            await reader.get(
                f"/api/v1/web/admin/webhooks/{subscription_id}/deliveries",
                params={"event_type": "lot"},
            )
        ).json()

        assert body["total"] == 0


# ── Personal access tokens and API keys ─────────────────────────────────


_TOKEN_SURFACES = [
    pytest.param(
        "/api/v1/web/users/me/personal-access-tokens/",
        [Permission.WRITE_PAT],
        PatOrmModel,
        id="pat",
    ),
    pytest.param(
        "/api/v1/web/admin/api-keys/",
        ["manage:api_keys"],
        ApiKeyOrmModel,
        id="api_key",
    ),
]


async def _seed_tokens(
    client: httpx.AsyncClient, db, base: str, model: type
) -> tuple[int, int, int]:
    """Three tokens: one created on day 1 that never expires, one created on
    day 3 whose expiry has passed, one created on day 3 that expires in a
    year. Creation dates and expiries are written straight to the rows."""
    now = datetime.now(UTC)
    shapes = [
        (_DAY_1, None),
        (_DAY_3, now - timedelta(days=1)),
        (_DAY_3, now + timedelta(days=365)),
    ]
    ids = []
    for index in range(len(shapes)):
        resp = await client.post(base, json={"name": f"Token {index}", "password": TEST_PASSWORD})
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    for token_id, (created, expires_at) in zip(ids, shapes, strict=True):
        await db.execute(
            update(model)
            .where(model.id == token_id)
            .values({"created": created, "expires_at": expires_at})
        )
    await db.commit()
    return ids[0], ids[1], ids[2]


@pytest.mark.parametrize(("base", "permissions", "model"), _TOKEN_SURFACES)
@pytest.mark.usefixtures("seeded_security")
class TestTokenListFilters:
    async def test_expiry_state(self, auth_client, db, base, permissions, model):
        client = await auth_client(permissions=permissions)
        never, expired, active = await _seed_tokens(client, db, base, model)

        assert _ids((await client.get(base, params={"expiry": "never"})).json()) == {never}
        assert _ids((await client.get(base, params={"expiry": "expired"})).json()) == {expired}
        assert _ids((await client.get(base, params={"expiry": "active"})).json()) == {active}
        unexpired = (await client.get(base, params={"expiry": "unexpired"})).json()
        assert _ids(unexpired) == {never, active}

    async def test_unknown_expiry_state_is_422(self, auth_client, base, permissions, model):
        client = await auth_client(permissions=permissions)

        assert (await client.get(base, params={"expiry": "soon"})).status_code == 422

    async def test_created_range(self, auth_client, db, base, permissions, model):
        client = await auth_client(permissions=permissions)
        never, expired, active = await _seed_tokens(client, db, base, model)

        early = (await client.get(base, params={"created_to": "2026-09-01"})).json()
        late = (await client.get(base, params={"created_from": "2026-09-02"})).json()

        assert _ids(early) == {never}
        assert _ids(late) == {expired, active}

    async def test_token_prefix(self, auth_client, db, base, permissions, model):
        client = await auth_client(permissions=permissions)
        never, expired, _ = await _seed_tokens(client, db, base, model)
        await db.execute(
            update(model).where(model.id == never).values({"token_prefix": "glados_zz99"})
        )
        await db.execute(
            update(model).where(model.id == expired).values({"token_prefix": "glados_aa11"})
        )
        await db.commit()

        body = (await client.get(base, params={"token_prefix": "ZZ9"})).json()

        assert _ids(body) == {never}


class TestApiKeyKindFilter:
    async def test_kind_splits_terminal_keys_from_standard_ones(self, auth_client, db):
        base = "/api/v1/web/admin/api-keys/"
        client = await auth_client(permissions=["manage:api_keys"])
        ids = []
        for name in ("Plain", "Terminal", "Terminal and more"):
            resp = await client.post(base, json={"name": name})
            assert resp.status_code == 201, resp.text
            ids.append(resp.json()["id"])
        plain, terminal, mixed = ids
        for key_id, grants in (
            (terminal, ["connect:terminals"]),
            (mixed, ["read:items", "connect:terminals"]),
            (plain, ["read:items"]),
        ):
            await db.execute(
                update(ApiKeyOrmModel).where(ApiKeyOrmModel.id == key_id).values(permissions=grants)
            )
        await db.commit()

        terminals = (await client.get(base, params={"kind": "terminal"})).json()
        standard = (await client.get(base, params={"kind": "standard"})).json()

        assert _ids(terminals) == {terminal, mixed}
        assert {row["kind"] for row in terminals["items"]} == {"terminal"}
        assert _ids(standard) == {plain}

    async def test_a_terminal_key_lookup_needs_one_row(self, auth_client, db):
        base = "/api/v1/web/admin/api-keys/"
        client = await auth_client(permissions=["manage:api_keys"])
        resp = await client.post(base, json={"name": "Terminal"})
        assert resp.status_code == 201, resp.text
        await db.execute(
            update(ApiKeyOrmModel)
            .where(ApiKeyOrmModel.id == resp.json()["id"])
            .values(
                permissions=["connect:terminals"], expires_at=datetime.now(UTC) - timedelta(days=1)
            )
        )
        await db.commit()
        params = {"kind": "terminal", "expiry": "unexpired", "limit": 1}

        assert (await client.get(base, params=params)).json()["total"] == 0

    async def test_unknown_kind_is_422(self, auth_client):
        client = await auth_client(permissions=["manage:api_keys"])

        resp = await client.get("/api/v1/web/admin/api-keys/", params={"kind": "robot"})

        assert resp.status_code == 422
