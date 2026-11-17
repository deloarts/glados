"""
The distribution of meeting notes over HTTP: downloading, printing and
sending the browser-built PDF with its journal entry and snapshot, the
version and issue checks, the issue labels, the attachment limit, a mail
server that refuses, the distribution list and snapshots, the recipient
suggestions, anonymising contacts and guests in snapshots, and the
meeting todos on the todo page.
"""

import hashlib
import json
from collections.abc import AsyncIterator
from collections.abc import Iterator
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest

from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.misc import get_custom_mail
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.application.services.custom_mail import CustomMail
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.exceptions import SmtpDeliveryError
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.adapters.inbound.api.deps import meeting_notes_journal as journal_deps
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from tests.integration.fakes import FakeLoginAttemptTracker

WRITE = [
    Permission.WRITE_MEETINGS,
    Permission.WRITE_PROJECTS,
    Permission.WRITE_CONTACTS,
    Permission.READ_CONTACTS,
]
MANAGE = [*WRITE, Permission.MANAGE_MEETINGS, Permission.SEND_MAIL]
BASE = "/api/v1/web/meetings/"
PDF = b"%PDF-1.7\n% meeting notes\n"


# ── Fakes ─────────────────────────────────────────────────────────────


class _MemoryStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.blobs[key] = data

    async def download(self, key: str) -> tuple[bytes, str]:
        return self.blobs[key], "application/octet-stream"

    async def delete(self, key: str) -> None:
        self.blobs.pop(key, None)

    def get_url(self, key: str, file_name: str | None = None) -> str:
        return f"memory://{key}"


class _Mail:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.refuse: str | None = None

    async def send_custom(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        reply_to: str | None = None,
        attachments: list[MailAttachment] | None = None,
    ) -> None:
        if self.refuse is not None:
            raise SmtpDeliveryError(self.refuse)
        self.sent.append(
            {"to": to, "cc": cc, "subject": subject, "attachments": list(attachments or [])}
        )


class _MailSettings:
    def __init__(self) -> None:
        self.mail = AdminMailSettings(
            id=1,
            enabled=True,
            host="smtp.example.com",
            port=587,
            user="noreply",
            password=None,
            from_address="noreply@example.com",
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=100,
            send_lock_minutes=60,
            alert_recipients=[],
            attachment_limit_mb=10,
        )

    async def get_mail(self) -> AdminMailSettings:
        return self.mail


class _Gateway:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes, int]] = []

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        self.sent.append((printer.name, payload, copies))
        return PrintDelivery()


@pytest.fixture
def storage() -> Iterator[_MemoryStorage]:
    memory = _MemoryStorage()
    app.dependency_overrides[get_optional_storage_adapter] = lambda: memory
    yield memory
    app.dependency_overrides.pop(get_optional_storage_adapter, None)


@pytest.fixture
def mail_settings() -> _MailSettings:
    return _MailSettings()


@pytest.fixture
def mail(mail_settings: _MailSettings) -> Iterator[_Mail]:
    fake = _Mail()
    custom = CustomMail(fake, FakeLoginAttemptTracker(), mail_settings)  # type: ignore[arg-type]
    app.dependency_overrides[get_custom_mail] = lambda: custom
    yield fake
    app.dependency_overrides.pop(get_custom_mail, None)


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> _Gateway:
    fake = _Gateway()
    monkeypatch.setattr(journal_deps, "get_printer_gateway", lambda: fake)
    return fake


@pytest.fixture
async def manager(auth_client) -> AsyncIterator[httpx.AsyncClient]:
    yield await auth_client(permissions=MANAGE)


@pytest.fixture
async def writer(auth_client) -> AsyncIterator[httpx.AsyncClient]:
    yield await auth_client(permissions=WRITE, username="writer", email="writer@example.com")


# ── Helpers ───────────────────────────────────────────────────────────


async def _me(client: httpx.AsyncClient) -> dict:
    return (await client.get("/api/v1/web/users/me")).json()


async def _created(response: httpx.Response) -> dict:
    assert response.status_code in (200, 201), response.text
    return response.json()


async def _customer(client, name="Muster Anlagenbau", email="office@muster.example"):
    return await _created(
        await client.post("/api/v1/web/customers/", json={"name": name, "email": email})
    )


async def _contact(client, name="Thomas Muster", email="t.b@example.com", **payload):
    return await _created(
        await client.post("/api/v1/web/contacts/", json={"name": name, "email": email, **payload})
    )


async def _project(client, number="26-0142", **payload):
    return await _created(
        await client.post("/api/v1/web/projects/", json={"project_number": number, **payload})
    )


async def _meeting(client, project_id: int, **payload):
    start = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
    body = {
        "name": "Design Review Gripper",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
        "project_id": project_id,
        **payload,
    }
    return await _created(await client.post(BASE, json=body))


async def _card(client, meeting_id, **payload):
    return await _created(await client.post(f"{BASE}{meeting_id}/cards", json=payload))


async def _get(client, meeting_id) -> dict:
    return (await client.get(f"{BASE}{meeting_id}")).json()


def _versions(meeting: dict, *, internal: bool = False) -> str:
    return json.dumps(
        [
            {"id": c["id"], "edit_version": c["edit_version"]}
            for c in meeting["cards"]
            if internal or not c["internal"]
        ]
    )


def _form(meeting: dict, *, issue: int = 0, draft: bool = True, **extra: Any) -> dict[str, Any]:
    return {
        "language": "enGB",
        "report_version": "1",
        "options": json.dumps({"include_todos": True, "include_internal": False}),
        "cards": _versions(meeting),
        "issue_number": str(issue),
        "draft": "true" if draft else "false",
        **extra,
    }


def _pdf(content: bytes = PDF) -> dict[str, Any]:
    return {"file": ("MTG notes.pdf", content, "application/pdf")}


async def _download(client, meeting: dict, **form: Any) -> httpx.Response:
    return await client.post(
        f"{BASE}{meeting['id']}/distribution/download", data=_form(meeting, **form), files=_pdf()
    )


async def _send(client, meeting: dict, **form: Any) -> httpx.Response:
    data = _form(meeting, issue=form.pop("issue", 1), draft=False)
    data.pop("draft")
    data.update({"to": "t.b@example.com", "subject": "Minutes", "html_body": "<p>Hi</p>"})
    data.update(form)
    return await client.post(f"{BASE}{meeting['id']}/distribution/send", data=data, files=_pdf())


async def _setup(manager: httpx.AsyncClient) -> tuple[dict, dict, dict]:
    """A meeting with a contact and a guest, an open card with a decision
    and a todo, and an internal card."""
    project = await _project(manager)
    contact = await _contact(manager)
    meeting = await _meeting(
        manager,
        project["id"],
        attendees=[
            {"kind": "contact", "contact_id": contact["id"]},
            {"kind": "guest", "name": "Paul Lorem", "email": "p.lorem@example.com"},
        ],
    )
    card = await _card(manager, meeting["id"], scope="Vacuum gripper", body="Cups in FKM.")
    await _card(manager, meeting["id"], scope="Margin", body="Keep it low.", internal=True)
    me = await _me(manager)
    await _created(
        await manager.post(
            f"{BASE}{meeting['id']}/cards/{card['id']}/decisions", json={"text": "FKM cups"}
        )
    )
    await _created(
        await manager.post(
            f"{BASE}{meeting['id']}/cards/{card['id']}/todos",
            json={"title": "Order cups", "owners": [{"user_id": me["id"]}]},
        )
    )
    return project, contact, await _get(manager, meeting["id"])


# ── Download and the journal ──────────────────────────────────────────


class TestDownload:
    async def test_a_download_is_journaled_with_its_snapshot(self, manager):
        _, contact, meeting = await _setup(manager)

        issue = (await manager.get(f"{BASE}{meeting['id']}/issue")).json()
        response = await _download(manager, meeting)

        assert issue["send"] == {"issue_number": 1, "draft": False, "revision": "1"}
        assert issue["print"] == {"issue_number": 0, "draft": True, "revision": "draft"}
        assert response.status_code == 201, response.text
        entry = response.json()
        assert entry["kind"] == "downloaded"
        assert entry["issue"]["revision"] == "draft"
        assert entry["sha256"] == hashlib.sha256(PDF).hexdigest()
        assert entry["byte_size"] == len(PDF)
        assert entry["options"]["include_internal"] is False

        after = await _get(manager, meeting["id"])
        assert after["last_printed_at"] is not None and after["issue_number"] == 0
        history = (await manager.get(f"{BASE}{meeting['id']}/history")).json()
        assert history[0]["kind"] == "downloaded"
        assert history[0]["details"]["journal_entry_id"] == entry["journal_entry_id"]
        assert history[0]["details"]["snapshot_id"] == entry["snapshot_id"]

        listed = (await manager.get(f"{BASE}{meeting['id']}/distribution")).json()
        assert [e["journal_entry_id"] for e in listed] == [entry["journal_entry_id"]]
        snapshot = (
            await manager.get(
                f"{BASE}{meeting['id']}/distribution/snapshots/{entry['snapshot_id']}"
            )
        ).json()
        open_card = meeting["cards"][0]
        assert [c["id"] for c in snapshot["cards"]] == [open_card["id"]]
        assert {
            key: snapshot["cards"][0][key] for key in ("scope", "body", "internal", "edit_version")
        } == {key: open_card[key] for key in ("scope", "body", "internal", "edit_version")}
        assert snapshot["cards"][0]["decisions"][0]["text"] == "FKM cups"
        assert snapshot["cards"][0]["todos"][0]["title"] == "Order cups"
        assert [(a["kind"], a["name"], a["contact_id"]) for a in snapshot["attendees"]] == [
            ("contact", "Thomas Muster", contact["id"]),
            ("guest", "Paul Lorem", None),
        ]
        assert snapshot["sha256"] == entry["sha256"]

        journal = (
            await manager.get(
                "/api/v1/web/report-journal",
                params={"document": "meeting_notes", "root_public_id": meeting["public_id"]},
            )
        ).json()
        assert [(j["action"], j["root_type"], j["revision"]) for j in journal] == [
            ("download", "meeting", "draft")
        ]

    async def test_a_changed_added_or_deleted_card_answers_409(self, manager):
        _, _, meeting = await _setup(manager)
        card = meeting["cards"][0]
        stale = await _download(
            manager,
            meeting,
            cards=json.dumps([{"id": card["id"], "edit_version": card["edit_version"] + 1}]),
        )
        missing = await _download(manager, meeting, cards="[]")
        internal = await _download(manager, meeting, cards=_versions(meeting, internal=True))
        wrong_issue = await _download(manager, meeting, issue=1, draft=False)
        not_pdf = await manager.post(
            f"{BASE}{meeting['id']}/distribution/download",
            data=_form(meeting),
            files=_pdf(b"hello"),
        )

        assert stale.status_code == 409
        assert stale.json()["code"] == "MeetingNotesOutdatedError"
        assert "Vacuum gripper" in stale.json()["detail"]
        assert missing.status_code == 409 and "added" in missing.json()["detail"]
        assert internal.status_code == 422
        assert wrong_issue.status_code == 409
        assert not_pdf.status_code == 422
        assert (await manager.get(f"{BASE}{meeting['id']}/distribution")).json() == []

    async def test_the_general_report_routes_refuse_meeting_notes(self, manager):
        _, _, meeting = await _setup(manager)

        download = await manager.post(
            "/api/v1/web/report-journal/downloads",
            json={
                "document": "meeting_notes",
                "root_public_id": meeting["public_id"],
                "facts": {"language": "enGB", "options": {}, "report_version": "1"},
                "byte_size": 10,
                "sha256": "a" * 64,
            },
        )

        assert download.status_code == 422
        assert download.json()["code"] == "PrintDocumentKindRefusedError"


# ── Print ─────────────────────────────────────────────────────────────


class TestPrint:
    async def _printer(self, client) -> dict:
        return await _created(
            await client.post(
                "/api/v1/web/printers/",
                json={
                    "name": "Office printer",
                    "kind": "ipp_document",
                    "host": "192.0.2.20",
                    "port": 631,
                    "transport": "ipp",
                },
            )
        )

    async def test_a_print_is_journaled_and_a_failed_one_is_not(self, auth_client, gateway):
        client = await auth_client(
            permissions=[*MANAGE, Permission.WRITE_PRINTERS, Permission.PRINT_DOCUMENTS]
        )
        _, _, meeting = await _setup(client)
        printer = await self._printer(client)
        url = f"{BASE}{meeting['id']}/distribution/print"

        printed = await client.post(
            url, data=_form(meeting, printer_id=str(printer["id"]), copies="2"), files=_pdf()
        )
        failed = await client.post(
            url, data=_form(meeting, printer_id=str(printer["id"] + 99)), files=_pdf()
        )

        assert printed.status_code == 200, printed.text
        body = printed.json()
        assert body["status"] == "sent" and body["entry"]["kind"] == "printed"
        assert body["entry"]["copies"] == 2
        assert gateway.sent == [("Office printer", PDF, 2)]
        assert failed.status_code == 200
        assert failed.json()["status"] == "failed" and failed.json()["entry"] is None
        listed = (await client.get(f"{BASE}{meeting['id']}/distribution")).json()
        assert [e["kind"] for e in listed] == ["printed"]

    async def test_printing_needs_print_rights(self, manager, gateway):
        _, _, meeting = await _setup(manager)

        response = await manager.post(
            f"{BASE}{meeting['id']}/distribution/print",
            data=_form(meeting, printer_id="1"),
            files=_pdf(),
        )

        assert response.status_code == 403
        assert gateway.sent == []


# ── Send ──────────────────────────────────────────────────────────────


class TestSend:
    async def test_a_send_mails_journals_and_raises_the_issue(self, manager, mail, storage):
        _, _, meeting = await _setup(manager)
        document = await _created(
            await manager.post(
                f"{BASE}{meeting['id']}/files",
                data={"category": "pdf"},
                files={"file": ("drawing.pdf", b"%PDF-1.4 drawing", "application/pdf")},
            )
        )

        response = await _send(
            manager,
            meeting,
            to="t.b@example.com; p.lorem@example.com",
            cc="writer@example.com",
            attach_file_ids=[str(document["id"])],
        )

        assert response.status_code == 201, response.text
        entry = response.json()
        assert entry["kind"] == "sent" and entry["issue"]["revision"] == "1"
        assert entry["recipients"] == ["t.b@example.com", "p.lorem@example.com"]
        assert entry["cc"] == ["writer@example.com"]
        assert mail.sent[0]["to"] == "t.b@example.com, p.lorem@example.com"
        assert [a.file_name for a in mail.sent[0]["attachments"]] == [
            "MTG notes.pdf",
            "drawing.pdf",
        ]
        after = await _get(manager, meeting["id"])
        assert after["issue_number"] == 1 and after["last_sent_at"] is not None
        history = (await manager.get(f"{BASE}{meeting['id']}/history")).json()
        assert history[0]["kind"] == "sent"
        assert history[0]["details"]["recipients"] == entry["recipients"]
        journal = (
            await manager.get(
                "/api/v1/web/report-journal",
                params={"document": "meeting_notes", "root_public_id": meeting["public_id"]},
            )
        ).json()
        assert journal[0]["action"] == "mail"
        assert journal[0]["recipients"] == [
            "t.b@example.com",
            "p.lorem@example.com",
            "writer@example.com",
        ]
        snapshot = (
            await manager.get(
                f"{BASE}{meeting['id']}/distribution/snapshots/{entry['snapshot_id']}"
            )
        ).json()
        assert [f["file_name"] for f in snapshot["attachments"]] == ["drawing.pdf"]
        assert snapshot["subject"] == "Minutes"

    async def test_the_print_label_follows_the_changes_since_the_send(self, manager, mail):
        _, _, meeting = await _setup(manager)
        assert (await _send(manager, meeting)).status_code == 201
        unchanged = (await manager.get(f"{BASE}{meeting['id']}/issue")).json()

        card = meeting["cards"][0]
        await _created(
            await manager.post(
                f"{BASE}{meeting['id']}/todos/{card['todos'][0]['id']}/done", json={}
            )
        )
        ticked = (await manager.get(f"{BASE}{meeting['id']}/issue")).json()
        await _created(
            await manager.put(
                f"{BASE}{meeting['id']}/cards/{card['id']}",
                json={
                    "scope": "Vacuum gripper",
                    "body": "Cups in NBR.",
                    "expected_edit_version": card["edit_version"],
                },
            )
        )
        changed = (await manager.get(f"{BASE}{meeting['id']}/issue")).json()
        stale_print = await _download(manager, await _get(manager, meeting["id"]), issue=1)

        assert unchanged["print"] == {"issue_number": 1, "draft": False, "revision": "1"}
        assert unchanged["send"]["issue_number"] == 2
        assert ticked["print"]["draft"] is False
        assert changed["print"] == {"issue_number": 1, "draft": True, "revision": "1-draft"}
        assert changed["changed_card_ids"] == [card["id"]]
        assert stale_print.status_code == 201
        assert stale_print.json()["issue"]["revision"] == "1-draft"

    async def test_a_refused_mail_journals_nothing(self, manager, mail):
        _, _, meeting = await _setup(manager)
        mail.refuse = "550 mailbox unavailable"

        response = await _send(manager, meeting)

        assert response.status_code == 502
        assert response.json()["code"] == "SmtpDeliveryError"
        assert (await manager.get(f"{BASE}{meeting['id']}/distribution")).json() == []
        assert (await _get(manager, meeting["id"]))["issue_number"] == 0

    async def test_attachments_over_the_limit_are_refused_by_name(
        self, manager, mail, mail_settings, storage
    ):
        _, _, meeting = await _setup(manager)
        mail_settings.mail.attachment_limit_mb = 1
        big = await _created(
            await manager.post(
                f"{BASE}{meeting['id']}/files",
                data={"category": "pdf"},
                files={"file": ("big.pdf", b"%PDF-1.4" + b"0" * 1_100_000, "application/pdf")},
            )
        )

        response = await _send(manager, meeting, attach_file_ids=[str(big["id"])])

        assert response.status_code == 413
        assert response.json()["code"] == "MailAttachmentsTooLargeError"
        assert "big.pdf" in response.json()["detail"]
        assert mail.sent == []

    async def test_sending_needs_send_mail_and_the_next_issue(self, manager, writer, mail):
        _, _, meeting = await _setup(manager)

        refused = await _send(writer, meeting)
        stale = await _send(manager, meeting, issue=2)

        assert refused.status_code == 403
        assert stale.status_code == 409
        assert mail.sent == []

    async def test_the_mail_template_default_is_served(self, manager):
        response = await manager.get(
            "/api/v1/web/mail/templates/default", params={"kind": "meeting_notes"}
        )

        assert response.status_code == 200
        assert response.json()["kind"] == "meeting_notes"


# ── Recipients ────────────────────────────────────────────────────────


class TestRecipients:
    async def test_suggestions_come_from_attendees_links_and_the_customer(self, manager):
        customer = await _customer(manager)
        linked = await _contact(
            manager, name="Anna Linked", email="anna@muster.example", customer_id=customer["id"]
        )
        other = await _contact(
            manager, name="Otto Other", email="otto@muster.example", customer_id=customer["id"]
        )
        attending = await _contact(
            manager, name="Doris Dist", email="anna@muster.example".replace("anna", "doris")
        )
        project = await _project(manager, customer_id=customer["id"])
        await _created(
            await manager.post(
                f"/api/v1/web/projects/{project['id']}/contacts",
                json={"contact_id": linked["id"], "receives_meeting_notes": True},
            )
        )
        meeting = await _meeting(
            manager,
            project["id"],
            attendees=[
                {"kind": "contact", "contact_id": attending["id"], "status": "distribution_only"},
                {"kind": "guest", "name": "Anna Again", "email": "ANNA@muster.example"},
                {"kind": "guest", "name": "No Mail"},
            ],
        )

        rows = (await manager.get(f"{BASE}{meeting['id']}/recipient-suggestions")).json()

        by_email = {r["email"].casefold(): r for r in rows}
        assert set(by_email) == {
            "doris@muster.example",
            "anna@muster.example",
            "otto@muster.example",
            "office@muster.example",
        }
        assert by_email["doris@muster.example"]["preselected"] is True
        assert by_email["doris@muster.example"]["sources"][0]["attendee_status"] == (
            "distribution_only"
        )
        assert by_email["anna@muster.example"]["preselected"] is True
        assert [s["kind"] for s in by_email["anna@muster.example"]["sources"]] == [
            "attendee",
            "project_contact",
            "customer_contact",
        ]
        assert by_email["otto@muster.example"]["preselected"] is False
        assert by_email["office@muster.example"]["sources"][0]["kind"] == "customer"
        assert [r["preselected"] for r in rows] == [True, True, False, False]
        assert other["id"] in {s["contact_id"] for s in by_email["otto@muster.example"]["sources"]}

    async def test_without_read_contacts_only_the_attendees_are_offered(self, manager, auth_client):
        _, _, meeting = await _setup(manager)
        reader = await auth_client(permissions=[], username="reader", email="reader@example.com")

        rows = (await reader.get(f"{BASE}{meeting['id']}/recipient-suggestions")).json()

        assert [r["email"] for r in rows] == ["t.b@example.com", "p.lorem@example.com"]


# ── Anonymisation ─────────────────────────────────────────────────────


class TestAnonymisation:
    async def test_anonymising_a_contact_blanks_its_copies_in_snapshots(self, manager, mail):
        _, contact, meeting = await _setup(manager)
        entry = (await _send(manager, meeting, cc="p.lorem@example.com")).json()

        done = await manager.post(f"/api/v1/web/contacts/{contact['id']}/anonymise")
        snapshot = (
            await manager.get(
                f"{BASE}{meeting['id']}/distribution/snapshots/{entry['snapshot_id']}"
            )
        ).json()
        journal = (
            await manager.get(
                "/api/v1/web/report-journal",
                params={"document": "meeting_notes", "root_public_id": meeting["public_id"]},
            )
        ).json()

        assert done.status_code == 200
        assert snapshot["attendees"][0]["name"] == "" and snapshot["attendees"][0]["email"] is None
        assert snapshot["attendees"][0]["anonymised"] is True
        assert snapshot["recipients"] == [""]
        assert snapshot["cc"] == ["p.lorem@example.com"]
        assert snapshot["sha256"] == entry["sha256"]
        assert journal[0]["recipients"] == ["", "p.lorem@example.com"]

    async def test_anonymising_a_guest_blanks_it_in_snapshots(self, manager, mail):
        _, _, meeting = await _setup(manager)
        entry = (await _send(manager, meeting, to="p.lorem@example.com")).json()
        guest = meeting["attendees"][1]

        response = await manager.post(f"{BASE}{meeting['id']}/attendees/{guest['id']}/anonymise")
        snapshot = (
            await manager.get(
                f"{BASE}{meeting['id']}/distribution/snapshots/{entry['snapshot_id']}"
            )
        ).json()

        assert response.status_code == 200
        assert snapshot["attendees"][1]["name"] == "" and snapshot["attendees"][1]["anonymised"]
        assert snapshot["recipients"] == [""]
        assert snapshot["attendees"][0]["name"] == "Thomas Muster"


# ── Todo page ─────────────────────────────────────────────────────────


class TestTodoSources:
    async def test_the_users_open_todos_of_valid_meetings_are_listed(self, manager, writer):
        project = await _project(manager)
        writer_id = (await _me(writer))["id"]
        meeting = await _meeting(manager, project["id"])
        card = await _card(manager, meeting["id"], scope="Electrical")
        url = f"{BASE}{meeting['id']}/cards/{card['id']}/todos"
        due = date.today().isoformat()
        mine = await _created(
            await manager.post(
                url, json={"title": "Wire it", "due_date": due, "owners": [{"user_id": writer_id}]}
            )
        )
        undated = await _created(
            await manager.post(url, json={"title": "Check", "owners": [{"user_id": writer_id}]})
        )
        done = await _created(
            await manager.post(url, json={"title": "Done", "owners": [{"user_id": writer_id}]})
        )
        await manager.post(f"{BASE}{meeting['id']}/todos/{done['id']}/done", json={})
        await manager.post(url, json={"title": "Not mine"})
        invalid = await _meeting(manager, project["id"], name="Wrong project")
        invalid_card = await _card(manager, invalid["id"])
        await manager.post(
            f"{BASE}{invalid['id']}/cards/{invalid_card['id']}/todos",
            json={"title": "Gone", "owners": [{"user_id": writer_id}]},
        )
        await manager.post(f"{BASE}{invalid['id']}/invalidate", json={"reason": "Wrong project"})

        body = (
            await writer.get("/api/v1/web/todo/sources", params={"include_lots": "false"})
        ).json()

        assert [t["todo_id"] for t in body["meeting_todos"]] == [mine["id"], undated["id"]]
        row = body["meeting_todos"][0]
        assert row == {
            "todo_id": mine["id"],
            "title": "Wire it",
            "due_date": due,
            "meeting_id": meeting["id"],
            "meeting_number": meeting["meeting_number"],
            "meeting_name": meeting["name"],
            "owner_kind": "project",
            "owner_id": project["id"],
            "card_id": card["id"],
            "card_scope": "Electrical",
        }
        others = (
            await manager.get("/api/v1/web/todo/sources", params={"include_lots": "false"})
        ).json()
        assert others["meeting_todos"] == []
