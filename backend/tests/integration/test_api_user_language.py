"""
`PUT /users/me/language` takes the language as a free query parameter, so the
endpoint itself refuses a value no Language member names before it reaches
the user, which only ever holds a member.
"""

BASE = "/api/v1/web/users/me"


class TestLanguageEndpoint:
    async def test_a_known_language_is_accepted_and_persisted(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.put(f"{BASE}/language", params={"language": "deAT"})
        assert response.status_code == 200, response.text
        assert response.json()["language"] == "deAT"

        get_response = await client.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["language"] == "deAT"

    async def test_an_unknown_language_is_rejected_with_422(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.put(f"{BASE}/language", params={"language": "frFR"})

        assert response.status_code == 422, response.text
        assert (await client.get(BASE)).json()["language"] == "enGB"
