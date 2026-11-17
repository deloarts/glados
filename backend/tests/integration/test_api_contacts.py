"""
Contacts over HTTP: create, read, list with its filters, update with the
edit version, archive and restore, anonymise, the mail recipients of a
supplier, the permissions that guard personal data, and the contacts group
of the global search.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._suppliers import seed_supplier

READ = [Permission.READ_CONTACTS]
# Anonymising a contact also needs manage:meetings, since it reaches the
# meetings that name the contact.
WRITE = [
    Permission.READ_CONTACTS,
    Permission.WRITE_CONTACTS,
    Permission.WRITE_PROJECTS,
    Permission.MANAGE_MEETINGS,
]

BASE = "/api/v1/web/contacts/"


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


@pytest.fixture
async def reader(auth_client):
    return await auth_client(permissions=READ, username="reader", email="reader@example.com")


@pytest.fixture
async def outsider(auth_client):
    return await auth_client(permissions=[], username="outsider", email="outsider@example.com")


async def _customer(client, name="Muster Anlagenbau"):
    response = await client.post("/api/v1/web/customers/", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def _contact(client, **payload):
    response = await client.post(BASE, json={"name": "Thomas Muster", **payload})
    assert response.status_code == 201, response.text
    return response.json()


# ── Create and read ───────────────────────────────────────────────────


class TestCreate:
    async def test_a_customer_contact_round_trips_with_its_organisation(self, writer):
        customer = await _customer(writer)
        created = await _contact(
            writer,
            role="Project lead",
            email="t.muster@example.com",
            phone="+43 000 000 00 12",
            mobile="+43 000 1234",
            note="Prefers mornings",
            customer_id=customer["id"],
        )

        fetched = (await writer.get(f"{BASE}{created['id']}")).json()

        assert fetched["role"] == "Project lead"
        assert fetched["email"] == "t.muster@example.com"
        assert fetched["mobile"] == "+43 000 1234"
        assert fetched["note"] == "Prefers mornings"
        assert fetched["customer_id"] == customer["id"]
        assert fetched["supplier_id"] is None
        assert fetched["organisation"] == {
            "kind": "customer",
            "id": customer["id"],
            "name": "Muster Anlagenbau",
            "archived": False,
        }
        assert fetched["archived"] is False
        assert fetched["anonymised_at"] is None

    async def test_blank_text_is_stored_as_null(self, writer):
        created = await _contact(writer, role="  ", phone="")

        assert created["role"] is None
        assert created["phone"] is None
        assert created["organisation"] is None

    async def test_a_supplier_contact_keeps_its_mail_flags(self, writer, db):
        await seed_supplier(db, 7)
        created = await _contact(
            writer, supplier_id=7, receives_request_mails=True, receives_order_mails=False
        )

        assert created["organisation"]["kind"] == "supplier"
        assert created["receives_request_mails"] is True
        assert created["receives_order_mails"] is False

    async def test_mail_flags_without_a_supplier_answer_422(self, writer):
        response = await writer.post(
            BASE, json={"name": "Paul Lorem", "receives_order_mails": True}
        )

        assert response.status_code == 422
        assert response.json()["code"] == "ContactMailFlagsInvalidError"

    async def test_two_organisations_answer_422(self, writer, db):
        await seed_supplier(db, 7)
        customer = await _customer(writer)

        response = await writer.post(
            BASE, json={"name": "Both", "customer_id": customer["id"], "supplier_id": 7}
        )

        assert response.status_code == 422
        assert response.json()["code"] == "ContactOrganisationInvalidError"

    async def test_an_unknown_customer_answers_422(self, writer):
        response = await writer.post(BASE, json={"name": "Nobody's", "customer_id": 999})

        assert response.status_code == 422
        assert response.json()["code"] == "ContactOrganisationInvalidError"

    async def test_an_invalid_email_answers_422(self, writer):
        response = await writer.post(BASE, json={"name": "Typo", "email": "not-an-address"})

        assert response.status_code == 422


# ── Permissions ───────────────────────────────────────────────────────


class TestPermissions:
    async def test_reading_needs_read_contacts(self, writer, outsider):
        created = await _contact(writer)

        assert (await outsider.get(BASE)).status_code == 403
        assert (await outsider.get(f"{BASE}{created['id']}")).status_code == 403

    async def test_writing_needs_write_contacts(self, writer, reader):
        created = await _contact(writer)

        assert (await reader.post(BASE, json={"name": "New"})).status_code == 403
        assert (await reader.post(f"{BASE}{created['id']}/archive")).status_code == 403
        assert (await reader.post(f"{BASE}{created['id']}/anonymise")).status_code == 403
        assert (await reader.get(f"{BASE}{created['id']}")).status_code == 200


# ── List ──────────────────────────────────────────────────────────────


class TestList:
    async def test_filters_by_organisation_and_kind(self, writer, db):
        await seed_supplier(db, 7)
        customer = await _customer(writer)
        await _contact(writer, name="Customer Person", customer_id=customer["id"])
        await _contact(writer, name="Supplier Person", supplier_id=7)
        await _contact(writer, name="Independent Person")

        def names(response):
            return [item["name"] for item in response.json()["items"]]

        assert names(await writer.get(BASE, params={"customer_id": customer["id"]})) == [
            "Customer Person"
        ]
        assert names(await writer.get(BASE, params={"supplier_id": 7})) == ["Supplier Person"]
        assert names(await writer.get(BASE, params={"organisation_kind": "none"})) == [
            "Independent Person"
        ]

    async def test_search_matches_the_organisation_name(self, writer):
        customer = await _customer(writer, "Stahlbau Sample")
        await _contact(writer, name="Eva", customer_id=customer["id"])
        await _contact(writer, name="Someone Else")

        body = (await writer.get(BASE, params={"search": "sample"})).json()

        assert [item["name"] for item in body["items"]] == ["Eva"]

    async def test_archived_contacts_show_only_when_asked(self, writer):
        created = await _contact(writer)
        await writer.post(f"{BASE}{created['id']}/archive")

        assert (await writer.get(BASE)).json()["total"] == 0
        assert (await writer.get(BASE, params={"include_archived": True})).json()["total"] == 1

    async def test_ordering_by_organisation_puts_contacts_without_one_last(self, writer):
        alpha = await _customer(writer, "Alpha")
        beta = await _customer(writer, "Beta")
        await _contact(writer, name="Nobody")
        await _contact(writer, name="Zoe", customer_id=beta["id"])
        await _contact(writer, name="Anna", customer_id=alpha["id"])

        for direction in ("asc", "desc"):
            body = (
                await writer.get(BASE, params={"order_by": "organisation", "order_dir": direction})
            ).json()
            names = [item["name"] for item in body["items"]]
            expected = ["Anna", "Zoe"] if direction == "asc" else ["Zoe", "Anna"]
            assert names == [*expected, "Nobody"]


# ── Update ────────────────────────────────────────────────────────────


class TestUpdate:
    async def test_an_update_replaces_the_fields_and_moves_the_version(self, writer, db):
        await seed_supplier(db, 7)
        created = await _contact(writer)

        response = await writer.put(
            f"{BASE}{created['id']}",
            json={
                "name": "Thomas B.",
                "supplier_id": 7,
                "receives_order_mails": True,
                "expected_edit_version": created["edit_version"],
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "Thomas B."
        assert body["organisation"]["kind"] == "supplier"
        assert body["receives_order_mails"] is True
        assert body["edit_version"] > created["edit_version"]
        assert body["changed"] is not None

    async def test_a_stale_version_answers_409(self, writer):
        created = await _contact(writer)
        await writer.put(
            f"{BASE}{created['id']}",
            json={"name": "First", "expected_edit_version": created["edit_version"]},
        )

        response = await writer.put(
            f"{BASE}{created['id']}",
            json={"name": "Second", "expected_edit_version": created["edit_version"]},
        )

        assert response.status_code == 409

    async def test_the_version_is_required(self, writer):
        created = await _contact(writer)

        response = await writer.put(f"{BASE}{created['id']}", json={"name": "No version"})

        assert response.status_code == 422


# ── Archive, restore, anonymise ───────────────────────────────────────


class TestArchiveAndAnonymise:
    async def test_archive_and_restore_are_idempotent(self, writer):
        created = await _contact(writer)

        for _ in range(2):
            archived = await writer.post(f"{BASE}{created['id']}/archive")
            assert archived.status_code == 200
            assert archived.json()["archived"] is True
        for _ in range(2):
            restored = await writer.post(f"{BASE}{created['id']}/restore")
            assert restored.status_code == 200
            assert restored.json()["archived"] is False

    async def test_anonymise_blanks_the_personal_data_and_archives(self, writer, db):
        await seed_supplier(db, 7)
        created = await _contact(
            writer,
            role="Sales",
            email="k.hypothetical@example.com",
            phone="+43 1",
            mobile="+43 2",
            note="Personal note",
            supplier_id=7,
            receives_order_mails=True,
        )

        response = await writer.post(f"{BASE}{created['id']}/anonymise")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == ""
        assert body["email"] is None
        assert body["phone"] is None
        assert body["mobile"] is None
        assert body["note"] is None
        assert body["receives_order_mails"] is False
        assert body["archived"] is True
        assert body["anonymised_at"] is not None
        assert body["role"] == "Sales"
        assert body["supplier_id"] == 7

    async def test_an_anonymised_contact_cannot_be_edited_or_restored(self, writer):
        created = await _contact(writer)
        anonymised = (await writer.post(f"{BASE}{created['id']}/anonymise")).json()

        update = await writer.put(
            f"{BASE}{created['id']}",
            json={"name": "Back", "expected_edit_version": anonymised["edit_version"]},
        )
        restore = await writer.post(f"{BASE}{created['id']}/restore")
        again = await writer.post(f"{BASE}{created['id']}/anonymise")

        assert update.status_code == 409
        assert update.json()["code"] == "ContactAnonymisedError"
        assert restore.status_code == 409
        assert again.status_code == 200


# ── Supplier mail recipients ──────────────────────────────────────────


class TestSupplierMailRecipients:
    async def test_lists_the_flagged_live_contacts_with_an_address(self, writer, db):
        await seed_supplier(db, 7)
        await _contact(
            writer,
            name="Karin",
            email="karin@example.com",
            supplier_id=7,
            receives_request_mails=True,
            receives_order_mails=True,
        )
        await _contact(
            writer,
            name="Martin",
            email="martin@example.com",
            supplier_id=7,
            receives_request_mails=True,
        )
        await _contact(writer, name="No Address", supplier_id=7, receives_order_mails=True)
        archived = await _contact(
            writer,
            name="Gone",
            email="gone@example.com",
            supplier_id=7,
            receives_order_mails=True,
        )
        await writer.post(f"{BASE}{archived['id']}/archive")

        body = (await writer.get("/api/v1/web/suppliers/7/mail-recipients")).json()

        assert [r["email"] for r in body["request"]] == ["karin@example.com", "martin@example.com"]
        assert [r["email"] for r in body["order"]] == ["karin@example.com"]

    async def test_no_flagged_contact_gives_empty_lists(self, writer, db):
        await seed_supplier(db, 7)

        body = (await writer.get("/api/v1/web/suppliers/7/mail-recipients")).json()

        assert body == {"supplier_id": 7, "request": [], "order": []}

    async def test_send_mail_suffices_and_nothing_else_does(self, auth_client, db):
        await seed_supplier(db, 7)
        sender = await auth_client(
            permissions=[Permission.SEND_MAIL], username="sender", email="sender@example.com"
        )
        other = await auth_client(permissions=[], username="other", email="other@example.com")

        assert (await sender.get("/api/v1/web/suppliers/7/mail-recipients")).status_code == 200
        assert (await other.get("/api/v1/web/suppliers/7/mail-recipients")).status_code == 403

    async def test_an_unknown_supplier_answers_404(self, writer):
        response = await writer.get("/api/v1/web/suppliers/999/mail-recipients")

        assert response.status_code == 404


# ── Global search ─────────────────────────────────────────────────────


class TestSearch:
    async def test_the_contacts_group_is_only_for_readers_of_contacts(self, writer, outsider):
        customer = await _customer(writer, "Muster Anlagenbau")
        await _contact(writer, name="Sabine Lipsum", role="Purchasing", customer_id=customer["id"])

        reader_body = (await writer.get("/api/v1/web/search/", params={"q": "lipsum"})).json()
        outsider_body = (await outsider.get("/api/v1/web/search/", params={"q": "lipsum"})).json()

        contacts = next(g for g in reader_body["groups"] if g["resource"] == "contacts")
        assert contacts["total"] == 1
        assert contacts["items"][0]["label"] == "Sabine Lipsum"
        assert contacts["items"][0]["subtitle"] == "Purchasing · Muster Anlagenbau"
        assert [g["resource"] for g in reader_body["groups"]][-1] == "contacts"
        assert all(g["resource"] != "contacts" for g in outsider_body["groups"])

    async def test_contacts_are_found_by_organisation_name(self, writer):
        customer = await _customer(writer, "Pneumatik Hypothetical")
        await _contact(writer, name="Karin", customer_id=customer["id"])

        body = (await writer.get("/api/v1/web/search/", params={"q": "hypothetical"})).json()

        contacts = next(g for g in body["groups"] if g["resource"] == "contacts")
        assert [hit["label"] for hit in contacts["items"]] == ["Karin"]
