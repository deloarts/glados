"""
HTTP-level coverage for `DELETE /api/v1/web/users/{user_id}` (DeleteUser).

DeleteUser is a soft delete (`is_active = False`), never a row removal, and
it deliberately does NOT revoke the target's sessions or PATs (that is
ForceLogoutUser's job, a separate action). The target's *existing* session
token still stops working on the very next request regardless, because
`get_current_active_user` rejects an inactive user outright. This file
pins that distinction: the session row survives, the token does not.
"""

from sqlalchemy import text

from src.modules.platform.domain.value_objects.permission import Permission

USERS = "/api/v1/web/users"


class TestPermission:
    async def test_requires_write_settings(self, auth_client, create_user):
        target = await create_user(username="victim", email="victim@example.com")
        actor = await auth_client(permissions=[])

        response = await actor.delete(f"{USERS}/{target.id}")

        assert response.status_code == 403

    async def test_write_settings_holder_can_delete_another_user(self, auth_client, create_user):
        target = await create_user(username="victim", email="victim@example.com")
        actor = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await actor.delete(f"{USERS}/{target.id}")

        assert response.status_code == 200


class TestSelfDeleteGuard:
    async def test_cannot_delete_own_account_even_with_write_settings(self, auth_client):
        actor = await auth_client(permissions=[Permission.WRITE_SETTINGS])
        me = (await actor.get("/api/v1/web/users/me")).json()

        response = await actor.delete(f"{USERS}/{me['id']}")

        assert response.status_code == 403
        # And the account is provably untouched.
        assert (await actor.get("/api/v1/web/users/me")).json()["is_active"] is True


class TestSystemUserGuard:
    async def test_system_user_can_never_be_deleted(self, auth_client, create_user):
        system_user = await create_user(
            username="system", email="system@example.com", is_systemuser=True
        )
        actor = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await actor.delete(f"{USERS}/{system_user.id}")

        assert response.status_code == 403


class TestDeactivationNotRemoval:
    async def test_target_is_deactivated_not_removed(self, auth_client, create_user, db):
        target = await create_user(username="victim", email="victim@example.com")
        actor = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await actor.delete(f"{USERS}/{target.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == target.id
        assert body["is_active"] is False

        # Still readable by id afterwards: a soft delete, not a row removal.
        readback = await actor.get(f"{USERS}/{target.id}")
        assert readback.status_code == 200
        assert readback.json()["is_active"] is False

        row_count = (
            await db.execute(
                text("SELECT COUNT(*) FROM user_table WHERE id = :id"), {"id": target.id}
            )
        ).scalar()
        assert row_count == 1


class TestSessionsSurviveButTokenStopsWorking:
    async def test_deleting_a_user_does_not_revoke_the_session_row_but_the_token_stops_working(
        self, auth_client, db
    ):
        """DeleteUser has no session_repo dependency at all (see
        get_delete_user_use_case in src/modules/platform/adapters/inbound/api/deps/users.py):
        unlike ForceLogoutUser, it never calls revoke_all_for_user. This pins
        that distinction: the session row is left alone by the delete, yet
        the target's existing token still stops authenticating on its very
        next request, because get_current_active_user rejects an inactive
        user regardless of session/token validity.
        """
        target_client = await auth_client(username="victim", email="victim@example.com")
        target_id = (await target_client.get("/api/v1/web/users/me")).json()["id"]
        actor = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        live_before = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM user_session_table "
                    "WHERE user_id = :uid AND revoked_at IS NULL"
                ),
                {"uid": target_id},
            )
        ).scalar()
        assert live_before == 1

        response = await actor.delete(f"{USERS}/{target_id}")
        assert response.status_code == 200

        live_after = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM user_session_table "
                    "WHERE user_id = :uid AND revoked_at IS NULL"
                ),
                {"uid": target_id},
            )
        ).scalar()
        assert live_after == live_before  # the row itself is untouched

        # ...yet the token that same row backs no longer authenticates.
        assert (await target_client.get("/api/v1/web/users/me")).status_code == 401


class TestUnknownUser:
    async def test_unknown_user_id_is_404(self, auth_client):
        actor = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await actor.delete(f"{USERS}/999999")

        assert response.status_code == 404
