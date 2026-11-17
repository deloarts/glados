"""
Backend half of the "Start page" feature (Settings polish batch):
`start_page` on `PUT /users/me`. Per-user only: unlike language and
date_format there is no tenant-wide default to fall back to, so a fresh
account always starts on StartPage.default() ("dashboard").
"""

BASE = "/api/v1/web/users/me"


class TestShippedDefault:
    async def test_a_freshly_created_user_starts_on_dashboard(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["start_page"] == "dashboard"


class TestStartPageValidation:
    async def test_an_unknown_value_is_rejected_with_422(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.put(BASE, json={"start_page": "not-a-page"})

        assert response.status_code == 422, response.text

    async def test_a_known_value_is_accepted_and_persisted(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.put(BASE, json={"start_page": "production"})
        assert response.status_code == 200, response.text
        assert response.json()["start_page"] == "production"

        # Persisted, not just echoed back: a fresh GET agrees.
        get_response = await client.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["start_page"] == "production"


class TestPartialUpdate:
    async def test_omitting_the_field_leaves_a_previously_set_value_untouched(self, auth_client):
        """The partial-update contract, same as every other preference on
        this endpoint: only an explicit value changes it."""
        client = await auth_client(permissions=[])
        await client.put(BASE, json={"start_page": "resources"})

        response = await client.put(BASE, json={"full_name": "Renamed"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["start_page"] == "resources"
        assert body["full_name"] == "Renamed"
