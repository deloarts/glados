"""
GET /host/values: the enumerated-value bootstrap endpoint every
authenticated user can read (no permission beyond being signed in). Covers
`start_pages` (Settings polish batch), the closed set the account page's
"Start" select and the frontend's post-login routing table both need.
"""

from src.modules.platform.domain.value_objects.start_page import StartPage

BASE = "/api/v1/web/host/values"


async def test_start_pages_lists_the_full_closed_set(auth_client):
    client = await auth_client(permissions=[])

    response = await client.get(BASE)

    assert response.status_code == 200, response.text
    assert response.json()["start_pages"] == StartPage.values()
