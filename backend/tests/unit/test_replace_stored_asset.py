"""
replace_stored_asset, the commit, upload and cleanup order every stored
asset replacement (branding images, login video, company logo, avatars)
runs through.
"""

import pytest

from src.modules.platform.application.services.storage_asset import replace_stored_asset


class _Storage:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._log.append(f"upload {key}")
        self.content_type = content_type

    async def delete(self, key: str) -> None:
        self._log.append(f"delete {key}")


class _Uow:
    def __init__(self, log: list[str], fail_commit_number: int | None = None) -> None:
        self._log = log
        self._fail = fail_commit_number
        self._commits = 0

    async def commit(self) -> None:
        self._commits += 1
        if self._commits == self._fail:
            self._log.append("commit failed")
            raise RuntimeError("commit failed")
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


async def _replace(
    log: list[str], uow: _Uow, *, key: str, old_key: str | None, storage: _Storage | None = None
) -> str:
    async def save() -> str:
        log.append("save")
        return "saved"

    return await replace_stored_asset(
        storage or _Storage(log),  # type: ignore[arg-type]
        uow,  # type: ignore[arg-type]
        key=key,
        old_key=old_key,
        data=b"x",
        save=save,
        label="test asset",
    )


async def test_replace_stored_asset_deletes_the_superseded_object_after_the_commit() -> None:
    log: list[str] = []

    saved = await _replace(log, _Uow(log), key="new.png", old_key="old.svg")

    assert saved == "saved"
    assert log == ["commit", "upload new.png", "save", "commit", "delete old.svg"]


async def test_replace_stored_asset_keeps_an_object_overwritten_in_place() -> None:
    log: list[str] = []

    await _replace(log, _Uow(log), key="same.png", old_key="same.png")

    assert log == ["commit", "upload same.png", "save", "commit"]


async def test_replace_stored_asset_removes_the_new_object_when_the_commit_fails() -> None:
    log: list[str] = []

    with pytest.raises(RuntimeError):
        await _replace(log, _Uow(log, fail_commit_number=2), key="new.png", old_key="old.png")

    assert log == ["commit", "upload new.png", "save", "commit failed", "delete new.png"]


async def test_replace_stored_asset_never_deletes_the_live_object_on_a_failed_same_key_save() -> (
    None
):
    log: list[str] = []

    with pytest.raises(RuntimeError):
        await _replace(log, _Uow(log, fail_commit_number=2), key="same.png", old_key="same.png")

    assert "delete same.png" not in log


@pytest.mark.parametrize(
    ("key", "expected"),
    [("public/logo.svg", "image/svg+xml"), ("public/favicon.ico", "image/x-icon")],
)
async def test_replace_stored_asset_stores_the_type_of_the_key_extension(
    key: str, expected: str
) -> None:
    log: list[str] = []
    storage = _Storage(log)

    await _replace(log, _Uow(log), key=key, old_key=None, storage=storage)

    assert storage.content_type == expected
