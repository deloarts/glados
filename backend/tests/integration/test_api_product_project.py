"""
The product and project verticals over HTTP, two soft-deleting aggregates
whose `get_by_id` resolves a row regardless of `archived`, like customer's.

Beyond repeating the CRUD shape, these cover behaviour customer doesn't
have: cross-aggregate foreign-key validation (a project referencing a
customer/product that must exist and must not be soft-deleted), and the
designated-user rules where a plain writer cannot assign work to someone
else but a manager can.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

WRITE = [Permission.WRITE_PROJECTS]
MANAGE = [Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


@pytest.fixture
async def manager(auth_client):
    return await auth_client(permissions=MANAGE)


async def _customer(client, name="ACME", vat=None):
    payload = {"name": name, "level": "A"}
    if vat:
        payload["vat_id"] = vat
    r = await client.post("/api/v1/web/customers/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _product(client, number="P-001", **kw):
    r = await client.post("/api/v1/web/products/", json={"product_number": number, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def _project(client, number="J-001", **kw):
    r = await client.post("/api/v1/web/projects/", json={"project_number": number, **kw})
    assert r.status_code == 201, r.text
    return r.json()


# ── Product CRUD ──────────────────────────────────────────────────────


class TestProductCrud:
    @pytest.mark.smoke
    async def test_create_read_round_trip(self, writer):
        created = await _product(writer, "P-100", description="a widget")

        fetched = await writer.get(f"/api/v1/web/products/{created['id']}")

        assert fetched.status_code == 200
        assert fetched.json()["product_number"] == "P-100"
        assert fetched.json()["description"] == "a widget"

    async def test_product_number_must_be_unique_among_live_products(self, writer):
        await _product(writer, "P-100")

        response = await writer.post("/api/v1/web/products/", json={"product_number": "P-100"})

        assert response.status_code != 201
        assert response.status_code < 500

    async def test_lookup_by_product_number(self, writer):
        created = await _product(writer, "P-100")

        response = await writer.get("/api/v1/web/products/number/P-100")

        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    async def test_missing_product_number_is_422(self, writer):
        assert (await writer.post("/api/v1/web/products/", json={})).status_code == 422

    async def test_unknown_product_is_404(self, writer):
        assert (await writer.get("/api/v1/web/products/999999")).status_code == 404

    async def test_update_persists(self, writer):
        created = await _product(writer, "P-100")

        updated = await writer.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    writer, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "description": "changed",
            },
        )

        assert updated.status_code == 200
        assert (await writer.get(f"/api/v1/web/products/{created['id']}")).json()[
            "description"
        ] == "changed"


MACHINE_DATA = {
    "designation": "Press 12",
    "machine_type": "HP-400",
    "installation_site": "Linz",
    "installation_location": "Hall 3",
    "planned_placing_on_market": "2027-03-01",
    "legal_basis": "regulation",
}


class TestProductMachineData:
    async def test_machine_data_round_trip(self, writer):
        created = await _product(writer, "P-100", **MACHINE_DATA)
        fetched = (await writer.get(f"/api/v1/web/products/{created['id']}")).json()
        assert {key: fetched[key] for key in MACHINE_DATA} == MACHINE_DATA

        # The update replaces the product's fields, so leaving them out clears them.
        updated = await writer.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    writer, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "legal_basis": "directive",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["legal_basis"] == "directive"
        assert updated.json()["designation"] is None
        assert updated.json()["planned_placing_on_market"] is None

    async def test_machine_data_is_validated(self, writer):
        for bad in ({"legal_basis": "guideline"}, {"designation": "x" * 201}):
            response = await writer.post(
                "/api/v1/web/products/", json={"product_number": "P-100", **bad}
            )
            assert response.status_code == 422, bad


class TestProductArchiveRestore:
    async def test_archived_product_still_readable_by_id(self, manager):
        """GET /{id} always resolves regardless of `archived`: a scanned or
        linked reference to an archived product must still work."""
        created = await _product(manager, "P-100")

        await manager.post(f"/api/v1/web/products/{created['id']}/archive")

        resp = await manager.get(f"/api/v1/web/products/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

    async def test_archived_product_is_not_findable_by_number(self, manager):
        """get_by_product_number filters archived rows, matching
        uniqueness's partial index."""
        await _product(manager, "P-100")
        listed = (await manager.get("/api/v1/web/products/")).json()["items"][0]

        await manager.post(f"/api/v1/web/products/{listed['id']}/archive")

        assert (await manager.get("/api/v1/web/products/number/P-100")).status_code == 404

    async def test_product_number_is_reusable_after_archive(self, manager):
        first = await _product(manager, "P-100")
        await manager.post(f"/api/v1/web/products/{first['id']}/archive")

        second = await manager.post("/api/v1/web/products/", json={"product_number": "P-100"})

        assert second.status_code == 201
        assert second.json()["id"] != first["id"]

    async def test_archiving_twice_is_idempotent(self, manager):
        created = await _product(manager, "P-100")

        first = await manager.post(f"/api/v1/web/products/{created['id']}/archive")
        second = await manager.post(f"/api/v1/web/products/{created['id']}/archive")

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["archived"] is True

    async def test_restore_unarchives(self, manager):
        created = await _product(manager, "P-100")
        await manager.post(f"/api/v1/web/products/{created['id']}/archive")

        resp = await manager.post(f"/api/v1/web/products/{created['id']}/restore")

        assert resp.status_code == 200
        assert resp.json()["archived"] is False
        assert (await manager.get("/api/v1/web/products/number/P-100")).status_code == 200


# ── Project CRUD ──────────────────────────────────────────────────────


class TestProjectCrud:
    @pytest.mark.smoke
    async def test_create_read_round_trip(self, writer):
        created = await _project(writer, "J-100", description="a job")

        fetched = await writer.get(f"/api/v1/web/projects/{created['id']}")

        assert fetched.status_code == 200
        assert fetched.json()["project_number"] == "J-100"

    async def test_lookup_by_project_number(self, writer):
        created = await _project(writer, "J-100")

        response = await writer.get("/api/v1/web/projects/number/J-100")

        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    async def test_project_number_must_be_unique_among_live_projects(self, writer):
        await _project(writer, "J-100")

        response = await writer.post("/api/v1/web/projects/", json={"project_number": "J-100"})

        assert response.status_code != 201
        assert response.status_code < 500

    async def test_project_number_is_reusable_after_delete(self, manager):
        first = await _project(manager, "J-100")
        await manager.delete(
            f"/api/v1/web/projects/{first['id']}",
            params={
                "expected_edit_version": await row_version(
                    manager, f"/api/v1/web/projects/{first['id']}"
                )
            },
        )

        second = await manager.post("/api/v1/web/projects/", json={"project_number": "J-100"})

        assert second.status_code == 201

    async def test_deleted_project_is_not_readable_by_id(self, manager):
        created = await _project(manager, "J-100")

        await manager.delete(
            f"/api/v1/web/projects/{created['id']}",
            params={
                "expected_edit_version": await row_version(
                    manager, f"/api/v1/web/projects/{created['id']}"
                )
            },
        )

        assert (await manager.get(f"/api/v1/web/projects/{created['id']}")).status_code == 404

    async def test_a_new_project_already_has_a_creation_changelog_entry(self, writer):
        created = await _project(writer, "J-100")

        response = await writer.get(f"/api/v1/web/projects/{created['id']}/changelog")

        assert response.status_code == 200
        entries = response.json()
        assert len(entries) == 1
        assert entries[0].endswith("Project created.")

    async def test_an_update_appends_a_diff_changelog_entry(self, writer):
        created = await _project(writer, "J-100", description="before")

        await writer.put(
            f"/api/v1/web/projects/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    writer, f"/api/v1/web/projects/{created['id']}"
                ),
                "project_number": "J-100",
                "description": "after",
            },
        )
        entries = (await writer.get(f"/api/v1/web/projects/{created['id']}/changelog")).json()

        assert len(entries) == 2
        assert "description" in entries[1]

    async def test_designated_user_id_must_be_positive(self, writer):
        response = await writer.post(
            "/api/v1/web/projects/", json={"project_number": "J-1", "designated_user_id": 0}
        )
        assert response.status_code == 422

    async def test_negative_time_budget_is_422(self, writer):
        response = await writer.post(
            "/api/v1/web/projects/",
            json={"project_number": "J-1", "production_time_budget": -5},
        )
        assert response.status_code == 422


# ── designated_user_id on update ──────────────────────────────────────
#
# The field is optional on update, as the schema (`int | None = None`)
# declares, so omitting it never answers 404 "Designated user #None does
# not exist." Update also consults ProductRules/ProjectRules, so the
# create-time rule "a non-manager cannot assign to someone else" cannot be
# bypassed by create-then-PUT.


class TestUpdateDesignatedUser:
    async def test_product_update_may_omit_designated_user(self, writer):
        created = await _product(writer, "P-100")

        response = await writer.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    writer, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "description": "changed",
            },
        )

        assert response.status_code == 200

    async def test_project_update_may_omit_designated_user(self, writer):
        created = await _project(writer, "J-100")

        response = await writer.put(
            f"/api/v1/web/projects/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    writer, f"/api/v1/web/projects/{created['id']}"
                ),
                "project_number": "J-100",
                "description": "changed",
            },
        )

        assert response.status_code == 200

    async def test_omitting_it_leaves_the_owner_unchanged(self, writer):
        """The safety property: a PUT that forgets the field must not
        silently transfer ownership to whoever saved last."""
        created = await _product(writer, "P-100")
        original_owner = created["designated_user_id"]

        updated = (
            await writer.put(
                f"/api/v1/web/products/{created['id']}",
                json={
                    "expected_edit_version": await row_version(
                        writer, f"/api/v1/web/products/{created['id']}"
                    ),
                    "product_number": "P-100",
                    "description": "changed",
                },
            )
        ).json()

        assert updated["designated_user_id"] == original_owner

    async def test_non_manager_cannot_reassign_a_product_to_another_user(
        self, auth_client, create_user
    ):
        """Closes the create-then-PUT bypass: create already forces a
        non-manager onto themselves, so update must not let them hand the
        record to someone else."""
        other = await create_user(username="other", email="other@example.com")
        client = await auth_client(permissions=WRITE)
        created = await _product(client, "P-100")

        response = await client.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "designated_user_id": other.id,
            },
        )

        assert response.status_code == 403

    async def test_non_manager_cannot_reassign_a_project_to_another_user(
        self, auth_client, create_user
    ):
        other = await create_user(username="other", email="other@example.com")
        client = await auth_client(permissions=WRITE)
        created = await _project(client, "J-100")

        response = await client.put(
            f"/api/v1/web/projects/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/projects/{created['id']}"
                ),
                "project_number": "J-100",
                "designated_user_id": other.id,
            },
        )

        assert response.status_code == 403

    async def test_non_manager_may_assign_to_themselves(self, auth_client):
        """Explicitly naming yourself is not a reassignment."""
        client = await auth_client(permissions=WRITE)
        created = await _product(client, "P-100")

        response = await client.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "designated_user_id": created["designated_user_id"],
            },
        )

        assert response.status_code == 200

    async def test_manager_may_reassign_to_another_user(self, auth_client, create_user):
        other = await create_user(username="other", email="other@example.com")
        client = await auth_client(permissions=MANAGE)
        created = await _product(client, "P-100")

        response = await client.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "designated_user_id": other.id,
            },
        )

        assert response.status_code == 200
        assert response.json()["designated_user_id"] == other.id

    async def test_manager_assigning_to_an_unknown_user_is_404(self, auth_client):
        client = await auth_client(permissions=MANAGE)
        created = await _product(client, "P-100")

        response = await client.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "designated_user_id": 999999,
            },
        )

        assert response.status_code == 404

    async def test_permission_is_checked_before_user_existence(self, auth_client):
        """A non-manager gets 403 for an id that does not exist either,
        otherwise the 403/404 split would leak which user ids are real."""
        client = await auth_client(permissions=WRITE)
        created = await _product(client, "P-100")

        response = await client.put(
            f"/api/v1/web/products/{created['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/products/{created['id']}"
                ),
                "product_number": "P-100",
                "designated_user_id": 999999,
            },
        )

        assert response.status_code == 403


# ── Cross-aggregate foreign keys ──────────────────────────────────────


class TestForeignKeyValidation:
    async def test_project_can_reference_an_existing_customer(self, writer):
        customer = await _customer(writer)

        created = await _project(writer, "J-100", customer_id=customer["id"])

        assert created["customer_id"] == customer["id"]

    async def test_project_referencing_an_unknown_customer_is_rejected(self, writer):
        response = await writer.post(
            "/api/v1/web/projects/", json={"project_number": "J-100", "customer_id": 999999}
        )

        assert response.status_code == 404
        assert response.status_code < 500

    async def test_project_referencing_an_unknown_product_is_rejected(self, writer):
        response = await writer.post(
            "/api/v1/web/projects/", json={"project_number": "J-100", "product_id": 999999}
        )

        assert response.status_code == 404

    async def test_project_can_reference_an_archived_customer(self, manager):
        """FK existence checks (create_project.py) resolve the referenced
        customer via the same `get_by_id` the direct GET endpoint uses,
        which resolves regardless of `archived`. An archived customer
        stays a valid FK target; it is only hidden from the default list
        and from name/vat_id-based uniqueness lookups. This is a
        deliberate consequence of `get_by_id` resolving unconditionally,
        applied consistently everywhere a use case looks up a referenced
        aggregate by id (see e.g. CreateBoughtItem's manufacturer_id
        check against Supplier), not a project/product-specific rule."""
        customer = await _customer(manager)
        await manager.post(f"/api/v1/web/customers/{customer['id']}/archive")

        response = await manager.post(
            "/api/v1/web/projects/",
            json={"project_number": "J-100", "customer_id": customer["id"]},
        )

        assert response.status_code == 201
        assert response.json()["customer_id"] == customer["id"]

    async def test_project_can_reference_an_archived_product(self, manager):
        product = await _product(manager, "P-100")
        await manager.post(f"/api/v1/web/products/{product['id']}/archive")

        response = await manager.post(
            "/api/v1/web/projects/",
            json={"project_number": "J-100", "product_id": product["id"]},
        )

        assert response.status_code == 201
        assert response.json()["product_id"] == product["id"]

    async def test_product_can_reference_an_archived_customer(self, manager):
        customer = await _customer(manager)
        await manager.post(f"/api/v1/web/customers/{customer['id']}/archive")

        response = await manager.post(
            "/api/v1/web/products/",
            json={"product_number": "P-100", "customer_id": customer["id"]},
        )

        assert response.status_code == 201
        assert response.json()["customer_id"] == customer["id"]
