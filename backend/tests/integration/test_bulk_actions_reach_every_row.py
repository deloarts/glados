"""
The bulk actions an admin takes in an incident reach every row, not just
the first page a repository read returns when no limit is given.
"""

from sqlalchemy import select

from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission

# More users than one default page holds, so a read that stops after the
# first page leaves some of them signed in.
_USERS = DEFAULT_PAGE_SIZE + 20


async def test_logging_out_all_users_reaches_every_active_user(
    db, create_user, auth_client
) -> None:
    for n in range(_USERS):
        await create_user(username=f"worker{n}", email=f"worker{n}@example.com")
    admin = await auth_client(
        permissions=[Permission.WRITE_SETTINGS], username="admin", email="admin@example.com"
    )

    response = await admin.delete("/api/v1/web/users/sessions")

    assert response.status_code == 200, response.text
    assert response.json()["count"] == _USERS
    versions = (
        await db.scalars(
            select(UserOrmModel.token_version).where(UserOrmModel.username.like("worker%"))
        )
    ).all()
    assert len(versions) == _USERS
    assert all(version > 0 for version in versions)
