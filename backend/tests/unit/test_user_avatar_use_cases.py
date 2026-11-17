"""
Unit tests for the avatar use cases (upload/delete/get). No database, no
HTTP, no storage backend: all dependencies are replaced with in-memory
fakes.

They cover that the storage key is randomized per upload
(users/avatars/{user_id}/{uuid4}{ext}) rather than derived from the user id,
and that managing another user's avatar requires Permission.WRITE_SETTINGS.
"""

import pytest

from src.modules.platform.application.use_cases.user.delete_user_avatar import DeleteUserAvatar
from src.modules.platform.application.use_cases.user.get_user_avatar import GetUserAvatar
from src.modules.platform.application.use_cases.user.upload_user_avatar import UploadUserAvatar
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import AvatarInvalidTypeError
from src.modules.platform.domain.exceptions import AvatarTooLargeError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None) -> None:
        self._users: dict[int, User] = {u.id: u for u in (users or [])}
        self.saved: User | None = None

    async def get_by_id(self, id: int) -> User | None:
        return self._users.get(id)

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        self.saved = user
        return user


class FakeUserPdmLinkRepository:
    """Empty stand-in: avatar use cases never change PDM links, they only
    read them back for the result's pdm_links field."""

    async def list_by_user(self, user_id: int) -> list:
        return []


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes, str]] = []
        self.deleted: list[str] = []
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.uploaded.append((key, data, content_type))
        self._objects[key] = (data, content_type)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self._objects.pop(key, None)

    async def download(self, key: str) -> tuple[bytes, str]:
        return self._objects[key]

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self._objects if k.startswith(prefix)]

    def get_url(self, key: str) -> str:
        return f"http://x/media/{key}"

    async def test_connection(self) -> None:
        return None


PNG_BYTES = b"\x89PNG\r\n\x1a\n"


# ── Key randomization ───────────────────────────────────────────────────


async def test_uploaded_key_is_not_derivable_from_the_user_id() -> None:
    repo = FakeUserRepository([make_user(id=7)])
    storage = FakeStorage()
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")

    key = storage.uploaded[0][0]
    assert key.startswith("users/avatars/7/")
    remainder = key[len("users/avatars/7/") :]
    stem, _, ext = remainder.partition(".")
    assert len(stem) == 32
    int(stem, 16)  # 32 hex chars
    assert ext == "png"


async def test_two_uploads_for_the_same_user_produce_different_keys() -> None:
    repo = FakeUserRepository([make_user(id=7)])
    storage = FakeStorage()
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")
    key1 = storage.uploaded[0][0]
    await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")
    key2 = storage.uploaded[1][0]

    assert key1 != key2


async def test_replacing_an_avatar_deletes_the_previous_key() -> None:
    repo = FakeUserRepository([make_user(id=7, avatar_key="users/avatars/7/old.jpg")])
    storage = FakeStorage()
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")

    assert "users/avatars/7/old.jpg" in storage.deleted


async def test_avatar_key_is_persisted_on_the_user() -> None:
    repo = FakeUserRepository([make_user(id=7)])
    storage = FakeStorage()
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")

    recorded_upload_key = storage.uploaded[0][0]
    assert repo.saved is not None
    assert repo.saved.avatar_key == recorded_upload_key


async def test_get_user_avatar_streams_the_persisted_key() -> None:
    storage = FakeStorage()
    await storage.upload("users/avatars/7/abc123.png", PNG_BYTES, "image/png")
    repo = FakeUserRepository([make_user(id=7, avatar_key="users/avatars/7/abc123.png")])
    uc = GetUserAvatar(user_repo=repo, storage=storage)

    data, content_type = await uc.execute(user_id=7)

    assert data == PNG_BYTES
    assert content_type == "image/png"


async def test_upload_without_storage_raises_storage_not_enabled() -> None:
    repo = FakeUserRepository([make_user(id=7)])
    uc = UploadUserAvatar(
        user_repo=repo, storage=None, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    with pytest.raises(StorageNotEnabledError):
        await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")


async def test_oversize_and_wrong_type_are_rejected() -> None:
    repo = FakeUserRepository([make_user(id=7)])
    storage = FakeStorage()
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    with pytest.raises(AvatarTooLargeError):
        await uc.execute(
            actor=make_user(id=7),
            user_id=7,
            data=b"x" * (6 * 1024 * 1024),
            content_type="image/png",
        )

    with pytest.raises(AvatarInvalidTypeError):
        await uc.execute(
            actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="application/pdf"
        )


async def test_content_not_matching_its_declared_type_is_rejected() -> None:
    """A JPEG payload declared as image/png passes the header allow-list
    check but must still be rejected once its magic bytes are checked."""
    repo = FakeUserRepository([make_user(id=7)])
    storage = FakeStorage()
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )
    jpeg_bytes = b"\xff\xd8\xff" + b"rest-of-the-file"

    with pytest.raises(AvatarInvalidTypeError):
        await uc.execute(
            actor=make_user(id=7), user_id=7, data=jpeg_bytes, content_type="image/png"
        )


# ── write:settings gate ─────────────────────────────────────────────────


async def test_actor_can_manage_own_avatar_without_any_permission() -> None:
    repo = FakeUserRepository([make_user(id=7, permissions=[])])
    storage = FakeStorage()
    upload_uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    result = await upload_uc.execute(
        actor=make_user(id=7, permissions=[]),
        user_id=7,
        data=PNG_BYTES,
        content_type="image/png",
    )

    assert result.id == 7


async def test_actor_cannot_manage_another_users_avatar_without_write_settings() -> None:
    repo = FakeUserRepository([make_user(id=7), make_user(id=8, permissions=[])])
    storage = FakeStorage()
    upload_uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )
    delete_uc = DeleteUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    with pytest.raises(InsufficientPermissionsError):
        await upload_uc.execute(
            actor=make_user(id=8, permissions=[]),
            user_id=7,
            data=PNG_BYTES,
            content_type="image/png",
        )

    with pytest.raises(InsufficientPermissionsError):
        await delete_uc.execute(actor=make_user(id=8, permissions=[]), user_id=7)


async def test_write_settings_actor_can_manage_another_users_avatar() -> None:
    repo = FakeUserRepository(
        [
            make_user(id=7, avatar_key="users/avatars/7/old.png"),
            make_user(id=8, permissions=[Permission.WRITE_SETTINGS]),
        ]
    )
    storage = FakeStorage()
    upload_uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )
    delete_uc = DeleteUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    await upload_uc.execute(
        actor=make_user(id=8, permissions=[Permission.WRITE_SETTINGS]),
        user_id=7,
        data=PNG_BYTES,
        content_type="image/png",
    )
    await delete_uc.execute(
        actor=make_user(id=8, permissions=[Permission.WRITE_SETTINGS]), user_id=7
    )

    assert repo.saved is not None
    assert repo.saved.avatar_key is None


async def test_systemuser_can_manage_another_users_avatar() -> None:
    repo = FakeUserRepository([make_user(id=7), make_user(id=8, is_systemuser=True)])
    storage = FakeStorage()
    upload_uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )
    delete_uc = DeleteUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    await upload_uc.execute(
        actor=make_user(id=8, is_systemuser=True, permissions=[]),
        user_id=7,
        data=PNG_BYTES,
        content_type="image/png",
    )
    await delete_uc.execute(actor=make_user(id=8, is_systemuser=True, permissions=[]), user_id=7)

    assert repo.saved is not None
    assert repo.saved.avatar_key is None


# ── Transaction and storage ordering ────────────────────────────────────


class SequencedUserRepository(FakeUserRepository):
    def __init__(self, log: list[str], users: list[User], fail_save: bool = False) -> None:
        super().__init__(users)
        self._log = log
        self._fail_save = fail_save

    async def save(self, user: User) -> User:
        if self._fail_save:
            self._log.append("save:failed")
            raise RuntimeError("database unavailable")
        self._log.append("save")
        return await super().save(user)


class SequencedStorage(FakeStorage):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._log.append(f"upload:{key}")
        await super().upload(key, data, content_type)

    async def download(self, key: str) -> tuple[bytes, str]:
        self._log.append(f"download:{key}")
        return await super().download(key)

    async def delete(self, key: str) -> None:
        self._log.append(f"delete:{key}")
        await super().delete(key)


class RecordingUow:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


async def test_upload_commits_then_uploads_then_saves_then_deletes_the_old_avatar() -> None:
    log: list[str] = []
    repo = SequencedUserRepository(log, [make_user(id=7, avatar_key="users/avatars/7/old.jpg")])
    storage = SequencedStorage(log)
    uc = UploadUserAvatar(
        user_repo=repo,
        storage=storage,
        link_repo=FakeUserPdmLinkRepository(),
        uow=RecordingUow(log),
    )

    await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")

    # The read transaction ends before the upload, the new key commits on
    # its own, and the old avatar goes only after that commit.
    new_key = storage.uploaded[0][0]
    assert log == [
        "commit",
        f"upload:{new_key}",
        "save",
        "commit",
        "delete:users/avatars/7/old.jpg",
    ]


async def test_failed_commit_deletes_the_new_avatar_and_keeps_the_old_one() -> None:
    log: list[str] = []
    repo = SequencedUserRepository(log, [make_user(id=7, avatar_key="users/avatars/7/old.jpg")])
    storage = SequencedStorage(log)

    class FailingSecondCommitUow(RecordingUow):
        commits = 0

        async def commit(self) -> None:
            self.commits += 1
            if self.commits == 2:
                self._log.append("commit:failed")
                raise RuntimeError("database unavailable")
            await super().commit()

    uc = UploadUserAvatar(
        user_repo=repo,
        storage=storage,
        link_repo=FakeUserPdmLinkRepository(),
        uow=FailingSecondCommitUow(log),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")

    new_key = storage.uploaded[0][0]
    assert log == ["commit", f"upload:{new_key}", "save", "commit:failed", f"delete:{new_key}"]
    assert "users/avatars/7/old.jpg" not in storage.deleted


async def test_failed_save_deletes_the_new_avatar_and_keeps_the_old_one() -> None:
    log: list[str] = []
    repo = SequencedUserRepository(
        log, [make_user(id=7, avatar_key="users/avatars/7/old.jpg")], fail_save=True
    )
    storage = SequencedStorage(log)
    uc = UploadUserAvatar(
        user_repo=repo, storage=storage, link_repo=FakeUserPdmLinkRepository(), uow=FakeUnitOfWork()
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await uc.execute(actor=make_user(id=7), user_id=7, data=PNG_BYTES, content_type="image/png")

    new_key = storage.uploaded[0][0]
    assert log == [f"upload:{new_key}", "save:failed", f"delete:{new_key}"]
    assert "users/avatars/7/old.jpg" not in storage.deleted


async def test_get_user_avatar_commits_before_the_download() -> None:
    log: list[str] = []
    storage = SequencedStorage(log)
    await storage.upload("users/avatars/7/abc123.png", PNG_BYTES, "image/png")
    log.clear()
    repo = FakeUserRepository([make_user(id=7, avatar_key="users/avatars/7/abc123.png")])
    uc = GetUserAvatar(user_repo=repo, storage=storage, uow=RecordingUow(log))

    await uc.execute(user_id=7)

    assert log == ["commit", "download:users/avatars/7/abc123.png"]
