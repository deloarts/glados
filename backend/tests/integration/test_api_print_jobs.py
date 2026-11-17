"""
HTTP-level coverage for `GET /api/v1/web/print-jobs/` (GetPrintJobs).
The use case has unit coverage
(tests/unit/test_get_print_jobs_use_case.py, permission gating only), and
this module drives it through real HTTP/routing/a real repository. It also
proves that printing and downloading a document persist their job rows,
read back through a separate request, so a use case that forgets to commit
its unit of work fails here instead of silently losing the row.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.adapters.outbound.persistence.models.print_template_model import (
    PrintTemplateOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_job_repository import (
    SqlAlchemyPrintJobRepository,
)
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType

PRINT_JOBS_URL = "/api/v1/web/print-jobs/"


async def _job(
    db,
    actor_id: int,
    *,
    classifier: PrintClassifier = PrintClassifier.MADE_ITEM_LABEL,
    root_type: PrintRootType = PrintRootType.MADE_ITEM,
    root_id: int = 1,
    status: PrintJobStatus = PrintJobStatus.SENT,
    trigger: PrintJobTrigger = PrintJobTrigger.MANUAL,
) -> int:
    job = await SqlAlchemyPrintJobRepository(db).save(
        PrintJob(
            id=0,
            created=datetime.now(UTC),
            template_id=None,
            printer_id=None,
            classifier=classifier,
            root_type=root_type,
            root_id=root_id,
            copies=1,
            status=status,
            error_message=None,
            rendered_zpl=None,
            document_bytes=None,
            trigger=trigger,
            source_event_id=None,
            actor_id=actor_id,
        )
    )
    await db.commit()
    return job.id


class TestPermission:
    async def test_requires_authentication(self, client):
        assert (await client.get(PRINT_JOBS_URL)).status_code == 401

    async def test_requires_read_settings(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get(PRINT_JOBS_URL)

        assert response.status_code == 403

    async def test_read_settings_holder_can_read(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await client.get(PRINT_JOBS_URL)

        assert response.status_code == 200


class TestResponseShapeAndData:
    async def test_lists_jobs_with_actor_name_and_supports_status_filter(self, auth_client, db):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        me = (await client.get("/api/v1/web/users/me")).json()

        sent_id = await _job(
            db, me["id"], status=PrintJobStatus.SENT, classifier=PrintClassifier.LOT_LABEL
        )
        failed_id = await _job(
            db, me["id"], status=PrintJobStatus.FAILED, classifier=PrintClassifier.LOT_DOCKET
        )

        all_jobs = (await client.get(PRINT_JOBS_URL)).json()
        assert all_jobs["total"] == 2
        ids = {row["id"] for row in all_jobs["items"]}
        assert {sent_id, failed_id} <= ids
        sent_row = next(r for r in all_jobs["items"] if r["id"] == sent_id)
        assert sent_row["actor_full_name"] == me["full_name"]
        assert sent_row["classifier"] == "lot_label"
        assert sent_row["trigger"] == "manual"

        failed_only = (await client.get(PRINT_JOBS_URL, params={"status": "failed"})).json()
        assert failed_only["total"] == 1
        assert failed_only["items"][0]["id"] == failed_id


async def _source_item_id(db) -> int:
    item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=1,
            dimension=None,
            material="Label stock",
            mass=None,
            note=None,
            order_code_1=None,
            order_code_2=None,
            status=SourceItemCatalogueStatus.ACTIVE,
            creator_id=1,
            approver_id=None,
            manufacturer_id=None,
            successor_item_id=None,
        )
    )
    await db.commit()
    return item.id


class TestPrintJobsArePersisted:
    async def test_a_print_persists_its_job_row(self, auth_client, db):
        # No template is seeded, so the print fails before any printer is
        # contacted, which still writes a failed job row.
        root_id = await _source_item_id(db)
        client = await auth_client(
            permissions=[Permission.PRINT_DOCUMENTS, Permission.READ_SETTINGS]
        )

        response = await client.post(
            "/api/v1/web/print/",
            json={
                "root_type": "source_item",
                "root_id": root_id,
                "items": [{"classifier": "source_item_label"}],
            },
        )

        assert response.status_code == 200, response.text
        job_id = response.json()[0]["id"]
        listed = (await client.get(PRINT_JOBS_URL)).json()
        assert [row["id"] for row in listed["items"]] == [job_id]
        assert listed["items"][0]["status"] == "failed"

    async def test_a_download_persists_its_job_row(self, auth_client, db):
        root_id = await _source_item_id(db)
        db.add(
            PrintTemplateOrmModel(
                created=date(2026, 1, 1),
                classifier="source_item_label",
                source="^XA^FDlabel^FS^XZ",
                enabled=True,
            )
        )
        await db.commit()
        client = await auth_client(
            permissions=[Permission.PRINT_DOCUMENTS, Permission.READ_SETTINGS]
        )

        response = await client.post(
            "/api/v1/web/print-templates/source_item_label/download",
            params={"root_type": "source_item", "root_id": root_id},
        )

        assert response.status_code == 200, response.text
        listed = (await client.get(PRINT_JOBS_URL)).json()
        assert listed["total"] == 1
        assert listed["items"][0]["classifier"] == "source_item_label"
        assert listed["items"][0]["status"] == "sent"
