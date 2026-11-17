"""
The contacts of products and projects over HTTP: linking, the meeting notes
flag, unlinking, a project's inherited contacts and how it mutes one, the
usage of contacts, and the permissions.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

WRITE = [Permission.READ_CONTACTS, Permission.WRITE_CONTACTS, Permission.WRITE_PROJECTS]


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


async def _contact(client, name):
    response = await client.post("/api/v1/web/contacts/", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def _product(client, number="P-001"):
    response = await client.post("/api/v1/web/products/", json={"product_number": number})
    assert response.status_code == 201, response.text
    return response.json()


async def _project(client, number="J-001", **payload):
    response = await client.post(
        "/api/v1/web/projects/", json={"project_number": number, **payload}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _names(body):
    return [entry["contact"]["name"] for entry in body]


# ── Product ───────────────────────────────────────────────────────────


class TestProductContacts:
    async def test_link_list_set_the_flag_and_unlink(self, writer):
        product = await _product(writer)
        thomas = await _contact(writer, "Thomas")
        anna = await _contact(writer, "Anna")
        url = f"/api/v1/web/products/{product['id']}/contacts"

        await writer.post(url, json={"contact_id": thomas["id"]})
        linked = await writer.post(
            url, json={"contact_id": anna["id"], "receives_meeting_notes": False}
        )

        assert linked.status_code == 200
        assert _names(linked.json()) == ["Anna", "Thomas"]
        assert [e["receives_meeting_notes"] for e in linked.json()] == [False, True]
        assert linked.json()[0]["contact"]["id"] == anna["id"]

        flagged = await writer.put(f"{url}/{anna['id']}", json={"receives_meeting_notes": True})
        assert [e["receives_meeting_notes"] for e in flagged.json()] == [True, True]

        unlinked = await writer.delete(f"{url}/{thomas['id']}")
        assert _names(unlinked.json()) == ["Anna"]
        assert _names((await writer.get(url)).json()) == ["Anna"]

    async def test_linking_twice_answers_409(self, writer):
        product = await _product(writer)
        thomas = await _contact(writer, "Thomas")
        url = f"/api/v1/web/products/{product['id']}/contacts"
        await writer.post(url, json={"contact_id": thomas["id"]})

        response = await writer.post(url, json={"contact_id": thomas["id"]})

        assert response.status_code == 409
        assert response.json()["code"] == "ContactAlreadyLinkedError"

    async def test_an_archived_contact_is_not_offered_for_new_links(self, writer):
        product = await _product(writer)
        thomas = await _contact(writer, "Thomas")
        await writer.post(f"/api/v1/web/contacts/{thomas['id']}/archive")

        response = await writer.post(
            f"/api/v1/web/products/{product['id']}/contacts", json={"contact_id": thomas["id"]}
        )

        assert response.status_code == 422
        assert response.json()["code"] == "ContactLinkInvalidError"

    async def test_an_archived_contact_stays_on_its_existing_links(self, writer):
        product = await _product(writer)
        thomas = await _contact(writer, "Thomas")
        url = f"/api/v1/web/products/{product['id']}/contacts"
        await writer.post(url, json={"contact_id": thomas["id"]})
        await writer.post(f"/api/v1/web/contacts/{thomas['id']}/archive")

        body = (await writer.get(url)).json()

        assert _names(body) == ["Thomas"]
        assert body[0]["contact"]["archived"] is True

    async def test_an_unknown_product_answers_404(self, writer):
        assert (await writer.get("/api/v1/web/products/999/contacts")).status_code == 404


# ── Project ───────────────────────────────────────────────────────────


class TestProjectContacts:
    async def test_a_project_inherits_its_products_contacts_before_its_own(self, writer):
        product = await _product(writer)
        project = await _project(writer, product_id=product["id"])
        thomas = await _contact(writer, "Thomas")
        anna = await _contact(writer, "Anna")
        await writer.post(
            f"/api/v1/web/products/{product['id']}/contacts", json={"contact_id": thomas["id"]}
        )

        body = (
            await writer.post(
                f"/api/v1/web/projects/{project['id']}/contacts", json={"contact_id": anna["id"]}
            )
        ).json()

        assert _names(body) == ["Thomas", "Anna"]
        assert [e["inherited"] for e in body] == [True, False]
        assert body[0]["product_receives_meeting_notes"] is True
        assert body[1]["product_receives_meeting_notes"] is None

    async def test_a_project_mutes_an_inherited_contact_and_follows_the_product_again(self, writer):
        product = await _product(writer)
        project = await _project(writer, product_id=product["id"])
        thomas = await _contact(writer, "Thomas")
        await writer.post(
            f"/api/v1/web/products/{product['id']}/contacts", json={"contact_id": thomas["id"]}
        )
        url = f"/api/v1/web/projects/{project['id']}/contacts/{thomas['id']}"

        muted = (await writer.put(url, json={"receives_meeting_notes": False})).json()

        assert muted[0]["receives_meeting_notes"] is False
        assert muted[0]["overridden"] is True
        assert muted[0]["product_receives_meeting_notes"] is True
        product_side = (await writer.get(f"/api/v1/web/products/{product['id']}/contacts")).json()
        assert product_side[0]["receives_meeting_notes"] is True

        unmuted = (await writer.put(url, json={"receives_meeting_notes": True})).json()

        assert unmuted[0]["receives_meeting_notes"] is True
        assert unmuted[0]["overridden"] is False

    async def test_an_inherited_contact_cannot_be_unlinked_or_linked_again(self, writer):
        product = await _product(writer)
        project = await _project(writer, product_id=product["id"])
        thomas = await _contact(writer, "Thomas")
        await writer.post(
            f"/api/v1/web/products/{product['id']}/contacts", json={"contact_id": thomas["id"]}
        )

        unlink = await writer.delete(
            f"/api/v1/web/projects/{project['id']}/contacts/{thomas['id']}"
        )
        link = await writer.post(
            f"/api/v1/web/projects/{project['id']}/contacts", json={"contact_id": thomas["id"]}
        )

        assert unlink.status_code == 409
        assert unlink.json()["code"] == "InheritedContactLinkError"
        assert link.status_code == 409
        assert link.json()["code"] == "ContactAlreadyLinkedError"

    async def test_a_project_without_a_product_has_only_its_own_contacts(self, writer):
        project = await _project(writer)
        anna = await _contact(writer, "Anna")
        url = f"/api/v1/web/projects/{project['id']}/contacts"
        await writer.post(url, json={"contact_id": anna["id"], "receives_meeting_notes": False})

        flagged = (
            await writer.put(f"{url}/{anna['id']}", json={"receives_meeting_notes": True})
        ).json()
        assert flagged[0]["receives_meeting_notes"] is True

        assert (await writer.delete(f"{url}/{anna['id']}")).json() == []

    async def test_setting_the_flag_of_an_unlinked_contact_answers_404(self, writer):
        project = await _project(writer)
        anna = await _contact(writer, "Anna")

        response = await writer.put(
            f"/api/v1/web/projects/{project['id']}/contacts/{anna['id']}",
            json={"receives_meeting_notes": True},
        )

        assert response.status_code == 404


# ── Usage and permissions ─────────────────────────────────────────────


class TestUsage:
    async def test_lists_the_products_and_projects_per_contact(self, writer):
        product = await _product(writer, "P-031")
        project = await _project(writer, "26-0142")
        thomas = await _contact(writer, "Thomas")
        anna = await _contact(writer, "Anna")
        await writer.post(
            f"/api/v1/web/products/{product['id']}/contacts", json={"contact_id": thomas["id"]}
        )
        await writer.post(
            f"/api/v1/web/projects/{project['id']}/contacts", json={"contact_id": thomas["id"]}
        )

        body = (
            await writer.get(
                "/api/v1/web/contact-usage/", params={"contact_ids": [thomas["id"], anna["id"]]}
            )
        ).json()

        assert [entry["contact_id"] for entry in body] == [thomas["id"], anna["id"]]
        assert [p["number"] for p in body[0]["products"]] == ["P-031"]
        assert [p["number"] for p in body[0]["projects"]] == ["26-0142"]
        assert body[1]["products"] == []
        assert body[1]["projects"] == []
        assert body[0]["meetings"] == []

    async def test_lists_the_meetings_a_contact_attends_or_owns_todos_in(self, auth_client):
        writer = await auth_client(
            permissions=[*WRITE, Permission.WRITE_MEETINGS],
            username="minutes",
            email="minutes@example.com",
        )
        project = await _project(writer, "26-0142")
        thomas = await _contact(writer, "Thomas")
        anna = await _contact(writer, "Anna")
        base = "/api/v1/web/meetings/"
        attended = await writer.post(
            base,
            json={
                "name": "Kick-off",
                "project_id": project["id"],
                "starts_at": "2026-10-28T13:00:00+00:00",
                "ends_at": "2026-10-28T14:00:00+00:00",
                "attendees": [{"kind": "contact", "contact_id": thomas["id"]}],
            },
        )
        owned = await writer.post(
            base,
            json={
                "name": "Design Review",
                "project_id": project["id"],
                "starts_at": "2026-11-06T09:00:00+00:00",
                "ends_at": "2026-11-06T10:00:00+00:00",
            },
        )
        card = await writer.post(f"{base}{owned.json()['id']}/cards", json={})
        # Twice in the same meeting still counts once.
        for title in ("Confirm the colour", "Confirm the delivery"):
            await writer.post(
                f"{base}{owned.json()['id']}/cards/{card.json()['id']}/todos",
                json={"title": title, "owners": [{"contact_id": thomas["id"]}]},
            )

        body = (
            await writer.get(
                "/api/v1/web/contact-usage/", params={"contact_ids": [thomas["id"], anna["id"]]}
            )
        ).json()

        assert [(m["meeting_number"], m["name"]) for m in body[0]["meetings"]] == [
            (owned.json()["meeting_number"], "Design Review"),
            (attended.json()["meeting_number"], "Kick-off"),
        ]
        assert body[1]["meetings"] == []


class TestPermissions:
    async def test_reading_needs_read_contacts(self, writer, auth_client):
        product = await _product(writer)
        url = f"/api/v1/web/products/{product['id']}/contacts"
        reader = await auth_client(
            permissions=[Permission.READ_CONTACTS], username="reader", email="reader@example.com"
        )
        outsider = await auth_client(permissions=[], username="out", email="out@example.com")

        assert (await outsider.get(url)).status_code == 403
        assert (await outsider.get("/api/v1/web/contact-usage/")).status_code == 403
        assert (await reader.get(url)).status_code == 200

    async def test_changing_follows_the_records_edit_rights_not_write_contacts(
        self, writer, auth_client
    ):
        product = await _product(writer)
        project = await _project(writer)
        thomas = await _contact(writer, "Thomas")
        product_url = f"/api/v1/web/products/{product['id']}/contacts"
        project_url = f"/api/v1/web/projects/{project['id']}/contacts"
        # Contact rights alone do not let someone change another person's record.
        contact_editor = await auth_client(
            permissions=[Permission.READ_CONTACTS, Permission.WRITE_CONTACTS],
            username="editor",
            email="editor@example.com",
        )
        # A project manager edits every product and project, without contact rights.
        manager = await auth_client(
            permissions=[Permission.READ_CONTACTS, Permission.MANAGE_PROJECTS],
            username="manager",
            email="manager@example.com",
        )

        for url in (product_url, project_url):
            body = {"contact_id": thomas["id"]}
            assert (await contact_editor.post(url, json=body)).status_code == 403
            assert (await manager.post(url, json=body)).status_code == 200
