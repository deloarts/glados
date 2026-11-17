"""
Item pictures: the picture shown is the photo, then the Data Portal
picture, then the CAD rendering; a writer replaces only its own source's
picture and removes the replaced blobs only after the commit; a person can
upload and delete the photo alone; a merge keeps the newer picture of each
source.
"""

import io
from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from PIL import Image

from src.modules.catalogue.application.services.item_picture_merge import merge_item_pictures
from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.application.use_cases.item_picture._kinds import BOUGHT_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture._kinds import SOURCE_ITEM_PICTURES
from src.modules.catalogue.application.use_cases.item_picture.delete_item_picture import (
    DeleteItemPicture,
)
from src.modules.catalogue.application.use_cases.item_picture.list_item_pictures import (
    ListItemPictures,
)
from src.modules.catalogue.application.use_cases.item_picture.upload_item_picture import (
    UploadItemPicture,
)
from src.modules.catalogue.domain.errors import ItemPictureInvalidTypeError
from src.modules.catalogue.domain.errors import ItemPictureNotFoundError
from src.modules.catalogue.domain.errors import ItemPictureTooLargeError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.item_picture_selection import pick_picture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.platform.domain.exceptions import ForbiddenError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.item_picture_fakes import FakeItemPictureRepository
from tests.unit.item_picture_fakes import FakePictureStorage
from tests.unit.item_picture_fakes import make_picture
from tests.unit.item_picture_fakes import png_bytes

PICTURE = ItemPictureSource.PICTURE
DATA_PORTAL = ItemPictureSource.DATA_PORTAL
CAD = ItemPictureSource.CAD_RENDERING


def _jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (10, 120, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


class _Items:
    def __init__(self, *ids: int) -> None:
        self.ids = set(ids)

    async def get_by_id(self, id: int) -> object | None:
        return object() if id in self.ids else None


def _writer() -> Any:
    return make_user(permissions=[Permission.WRITE_SOURCE_ITEMS])


# ── Selection ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("sources", "shown"),
    [
        ([CAD, DATA_PORTAL, PICTURE], PICTURE),
        ([CAD, DATA_PORTAL], DATA_PORTAL),
        ([CAD], CAD),
        ([], None),
    ],
)
def test_the_photo_wins_then_the_portal_picture_then_the_cad_rendering(
    sources: list[ItemPictureSource], shown: ItemPictureSource | None
) -> None:
    picked = pick_picture(make_picture(ItemKind.BOUGHT, 1, s) for s in sources)
    assert (picked.source if picked else None) == shown


def test_a_missing_variant_is_served_by_the_other_one() -> None:
    thumbnail_only = make_picture(ItemKind.MADE, 1, CAD, image_path=None, thumbnail_path="t.png")
    image_only = make_picture(ItemKind.MADE, 1, CAD, image_path="i.png", thumbnail_path=None)

    assert thumbnail_only.blob(ItemPictureVariant.IMAGE) == ("t.png", "image/png")
    assert image_only.blob(ItemPictureVariant.THUMBNAIL) == ("i.png", "image/png")


# ── Store ────────────────────────────────────────────────────────────


async def test_staging_replaces_only_the_same_sources_picture() -> None:
    photo = make_picture(ItemKind.BOUGHT, 1, PICTURE, picture_id=1)
    old_cad = make_picture(
        ItemKind.BOUGHT, 1, CAD, picture_id=2, image_path="old.png", thumbnail_path="old-t.png"
    )
    repo = FakeItemPictureRepository([photo, old_cad])
    storage = FakePictureStorage({"old.png": b"x", "old-t.png": b"x"})
    store = ItemPictureStore(repo, storage)  # type: ignore[arg-type]

    staged = await store.stage(ItemKind.BOUGHT, 1, CAD, _jpeg(800, 400), "cad.jpg", 9)

    assert {p.source for p in repo.pictures.values()} == {PICTURE, CAD}
    assert staged.picture.uploaded_by_user_id == 9
    assert storage.deleted == []  # nothing goes before the caller commits
    await store.finish(staged)
    assert storage.deleted == ["old.png", "old-t.png"]


async def test_the_thumbnail_is_derived_from_the_image() -> None:
    storage = FakePictureStorage()
    store = ItemPictureStore(FakeItemPictureRepository(), storage)  # type: ignore[arg-type]

    staged = await store.stage(ItemKind.SOURCE, 3, PICTURE, _jpeg(2000, 1000), "p.jpg", 1)

    assert staged.picture.thumbnail_path is not None
    with Image.open(io.BytesIO(storage.blobs[staged.picture.thumbnail_path][0])) as thumbnail:
        assert thumbnail.size == (512, 512)  # padded to a square, then shrunk


async def test_a_thumbnail_only_picture_stores_no_image() -> None:
    storage = FakePictureStorage()
    store = ItemPictureStore(FakeItemPictureRepository(), storage)  # type: ignore[arg-type]

    staged = await store.stage(
        ItemKind.MADE, 1, CAD, png_bytes(), "render.png", 1, thumbnail_only=True
    )

    assert staged.picture.image_path is None
    assert list(storage.blobs) == [staged.picture.thumbnail_path]


async def test_data_that_is_no_image_is_refused_before_anything_is_stored() -> None:
    storage = FakePictureStorage()
    store = ItemPictureStore(FakeItemPictureRepository(), storage)  # type: ignore[arg-type]

    with pytest.raises(ItemPictureInvalidTypeError):
        await store.stage(ItemKind.MADE, 1, CAD, b"not an image", "x.png", 1)
    assert storage.blobs == {}


async def test_a_failed_upload_removes_the_blobs_already_stored() -> None:
    class _FailingSecondUpload(FakePictureStorage):
        async def upload(self, key: str, data: bytes, content_type: str) -> None:
            if self.blobs:
                raise OSError("storage down")
            await super().upload(key, data, content_type)

    storage = _FailingSecondUpload()
    store = ItemPictureStore(FakeItemPictureRepository(), storage)  # type: ignore[arg-type]

    with pytest.raises(OSError):
        await store.stage(ItemKind.MADE, 1, PICTURE, png_bytes(), "p.png", 1)
    assert storage.blobs == {}


# ── Upload and delete ────────────────────────────────────────────────


def _upload(repo: FakeItemPictureRepository, storage: FakePictureStorage) -> UploadItemPicture:
    return UploadItemPicture(
        SOURCE_ITEM_PICTURES,
        _Items(3),
        repo,
        storage,  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
    )


async def test_an_uploaded_photo_is_the_picture_shown() -> None:
    repo = FakeItemPictureRepository([make_picture(ItemKind.SOURCE, 3, CAD)])
    result = await _upload(repo, FakePictureStorage()).execute(
        _writer(), 3, _jpeg(50, 50), "photo.jpg", "image/jpeg"
    )

    assert (result.source, result.in_use) == (PICTURE, True)
    assert {p.source for p in repo.pictures.values()} == {PICTURE, CAD}


@pytest.mark.parametrize(
    ("data", "content_type", "error"),
    [
        (b"%PDF", "application/pdf", ItemPictureInvalidTypeError),
        (b"x" * (10 * 1024 * 1024 + 1), "image/png", ItemPictureTooLargeError),
    ],
    ids=["not-an-image", "over-the-size-cap"],
)
async def test_an_upload_must_be_a_small_enough_image(
    data: bytes, content_type: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        await _upload(FakeItemPictureRepository(), FakePictureStorage()).execute(
            _writer(), 3, data, "f", content_type
        )


async def test_uploading_needs_the_write_permission_and_an_existing_item() -> None:
    upload = _upload(FakeItemPictureRepository(), FakePictureStorage())
    with pytest.raises(ForbiddenError):
        await upload.execute(make_user(), 3, png_bytes(), "p.png", "image/png")
    with pytest.raises(SourceItemNotFoundError):
        await upload.execute(_writer(), 99, png_bytes(), "p.png", "image/png")


async def test_the_editable_check_runs_before_anything_is_stored() -> None:
    storage = FakePictureStorage()

    async def refuse(item: object) -> None:
        raise ForbiddenError("older revision")

    upload = UploadItemPicture(
        SOURCE_ITEM_PICTURES,
        _Items(3),
        FakeItemPictureRepository(),
        storage,  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
        editable_check=refuse,
    )
    with pytest.raises(ForbiddenError):
        await upload.execute(_writer(), 3, png_bytes(), "p.png", "image/png")
    assert storage.blobs == {}


async def test_deleting_removes_only_the_photo_and_its_blobs() -> None:
    repo = FakeItemPictureRepository(
        [
            make_picture(ItemKind.SOURCE, 3, PICTURE, image_path="p.png", thumbnail_path="p-t.png"),
            make_picture(ItemKind.SOURCE, 3, CAD),
        ]
    )
    storage = FakePictureStorage()
    delete = DeleteItemPicture(
        SOURCE_ITEM_PICTURES,
        _Items(3),
        repo,
        storage,  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
    )

    await delete.execute(_writer(), 3)

    assert {p.source for p in repo.pictures.values()} == {CAD}
    assert storage.deleted == ["p.png", "p-t.png"]
    with pytest.raises(ItemPictureNotFoundError):
        await delete.execute(_writer(), 3)


# ── Listing ──────────────────────────────────────────────────────────


async def test_the_listing_orders_by_precedence_and_marks_the_picture_shown() -> None:
    repo = FakeItemPictureRepository(
        [
            make_picture(ItemKind.BOUGHT, 1, CAD),
            make_picture(ItemKind.BOUGHT, 1, DATA_PORTAL),
            make_picture(ItemKind.BOUGHT, 2, CAD),
        ]
    )
    listing = ListItemPictures(BOUGHT_ITEM_PICTURES, _Items(1, 2), repo)

    pictures = await listing.execute(1)
    in_use = await listing.execute_in_use([1, 2, 3])

    assert [(p.source, p.in_use) for p in pictures] == [(DATA_PORTAL, True), (CAD, False)]
    assert sorted((r.item_id, r.source) for r in in_use) == [(1, DATA_PORTAL), (2, CAD)]


# ── Merge ────────────────────────────────────────────────────────────


async def test_a_merge_keeps_the_newer_picture_of_each_source() -> None:
    early = datetime(2026, 1, 1, tzinfo=UTC)
    late = datetime(2026, 6, 1, tzinfo=UTC)
    repo = FakeItemPictureRepository(
        [
            make_picture(ItemKind.MADE, 1, PICTURE, picture_id=1, created=late),
            make_picture(ItemKind.MADE, 1, CAD, picture_id=2, created=early),
            make_picture(ItemKind.MADE, 2, PICTURE, picture_id=3, created=early),
            make_picture(ItemKind.MADE, 2, CAD, picture_id=4, created=late),
        ]
    )

    await merge_item_pictures(repo, ItemKind.MADE, source_id=1, target_id=2)

    kept = {p.source: p.id for p in await repo.get_by_item(ItemKind.MADE, 2)}
    assert kept == {PICTURE: 1, CAD: 4}
    assert await repo.get_by_item(ItemKind.MADE, 1) == []
