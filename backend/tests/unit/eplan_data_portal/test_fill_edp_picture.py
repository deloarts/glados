"""
The picture worker: a linked item gets the portal part's picture as its
Data Portal picture whatever other pictures it has, an unlinked one loses
it, a picture already fetched for the same part is kept, and nothing
happens while the portal or storage is off.
"""

import io
from dataclasses import dataclass
from dataclasses import field

from PIL import Image

from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.external_data.application.use_cases.eplan_data_portal.fill_edp_picture import (
    FillBoughtItemEdpPicture,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from tests.unit.item_picture_fakes import FakeItemPictureRepository
from tests.unit.item_picture_fakes import FakePictureStorage
from tests.unit.item_picture_fakes import make_picture

PICTURE_URL = "https://blob.example.test/p.png"


def _png(side: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (side, side), (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


@dataclass
class _Item:
    id: int = 7
    archived: bool = False
    edp_part_id: int | None = 451627


class _Items:
    def __init__(self, item: _Item | None) -> None:
        self.item = item

    async def get_by_id(self, item_id: int) -> _Item | None:
        return self.item


class _Settings:
    def __init__(self, settings: AdminEdpSettings) -> None:
        self.settings = settings

    async def get_edp(self) -> AdminEdpSettings:
        return self.settings


@dataclass
class _Actor:
    id: int = 1


class _Users:
    async def get_by_username(self, username: str) -> _Actor:
        return _Actor()


class _Uow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


@dataclass
class _Portal:
    picture: bytes | None
    connections: list[EdpConnection] = field(default_factory=list)

    def factory(self, connection: EdpConnection) -> "_Portal":
        self.connections.append(connection)
        return self

    async def get_parts(self, part_ids: list[int]) -> list[EdpPart]:
        return [
            EdpPart(
                part_id=part_ids[0],
                part_number="SIE.X",
                order_number=None,
                type_number=None,
                picture_url=PICTURE_URL,
            )
        ]

    async def fetch_picture(self, url: str) -> bytes | None:
        return self.picture


def _worker(
    *,
    item: _Item | None = None,
    pictures: FakeItemPictureRepository | None = None,
    storage: FakePictureStorage | None = None,
    settings: AdminEdpSettings | None = None,
    picture: bytes | None = None,
    with_storage: bool = True,
) -> tuple[FillBoughtItemEdpPicture, _Portal, FakeItemPictureRepository]:
    portal = _Portal(picture=_png(1024) if picture is None else picture)
    repo = pictures or FakeItemPictureRepository()
    store = ItemPictureStore(repo, storage or FakePictureStorage()) if with_storage else None
    worker = FillBoughtItemEdpPicture(
        item_repo=_Items(item if item is not None else _Item()),  # type: ignore[arg-type]
        picture_repo=repo,
        settings_repo=_Settings(  # type: ignore[arg-type]
            settings or AdminEdpSettings(id=1, enabled=True, pat="token")
        ),
        user_repo=_Users(),  # type: ignore[arg-type]
        portal_factory=portal.factory,  # type: ignore[arg-type]
        store=store,
        uow=_Uow(),
    )
    return worker, portal, repo


EVENT = BoughtItemEdpPictureRequested(item_id=7)


def _sources(repo: FakeItemPictureRepository) -> set[ItemPictureSource]:
    return {p.source for p in repo.pictures.values()}


async def test_edp_picture_is_stored_beside_a_photo_and_a_cad_rendering() -> None:
    repo = FakeItemPictureRepository(
        [
            make_picture(ItemKind.BOUGHT, 7, ItemPictureSource.PICTURE),
            make_picture(ItemKind.BOUGHT, 7, ItemPictureSource.CAD_RENDERING),
        ]
    )
    storage = FakePictureStorage()
    worker, portal, _ = _worker(pictures=repo, storage=storage)

    await worker.execute(EVENT)

    assert _sources(repo) == set(ItemPictureSource)
    stored = await repo.get_by_source(ItemKind.BOUGHT, 7, ItemPictureSource.DATA_PORTAL)
    assert stored is not None
    assert stored.file_name == "edp-451627.png"
    assert stored.image_path is not None and stored.thumbnail_path is not None
    with Image.open(io.BytesIO(storage.blobs[stored.thumbnail_path][0])) as thumbnail:
        assert max(thumbnail.size) <= 512
    assert portal.connections[0].pat == "token"


async def test_edp_picture_already_fetched_for_the_part_is_kept() -> None:
    repo = FakeItemPictureRepository(
        [
            make_picture(
                ItemKind.BOUGHT, 7, ItemPictureSource.DATA_PORTAL, file_name="edp-451627.png"
            )
        ]
    )
    worker, portal, _ = _worker(pictures=repo)

    await worker.execute(EVENT)

    assert portal.connections == []


async def test_a_new_part_replaces_the_previous_edp_picture_and_its_blobs() -> None:
    old = make_picture(
        ItemKind.BOUGHT,
        7,
        ItemPictureSource.DATA_PORTAL,
        file_name="edp-1.png",
        image_path="old.png",
        thumbnail_path="old-thumbnail.png",
    )
    repo = FakeItemPictureRepository([old])
    storage = FakePictureStorage({"old.png": b"x", "old-thumbnail.png": b"x"})
    worker, _, _ = _worker(pictures=repo, storage=storage)

    await worker.execute(EVENT)

    stored = await repo.get_by_source(ItemKind.BOUGHT, 7, ItemPictureSource.DATA_PORTAL)
    assert stored is not None and stored.file_name == "edp-451627.png"
    assert storage.deleted == ["old.png", "old-thumbnail.png"]


async def test_an_unlinked_item_loses_its_edp_picture_only() -> None:
    repo = FakeItemPictureRepository(
        [
            make_picture(ItemKind.BOUGHT, 7, ItemPictureSource.PICTURE),
            make_picture(
                ItemKind.BOUGHT,
                7,
                ItemPictureSource.DATA_PORTAL,
                image_path="edp.png",
                thumbnail_path="edp-thumbnail.png",
            ),
        ]
    )
    storage = FakePictureStorage()
    worker, portal, _ = _worker(item=_Item(edp_part_id=None), pictures=repo, storage=storage)

    await worker.execute(EVENT)

    assert _sources(repo) == {ItemPictureSource.PICTURE}
    assert storage.deleted == ["edp.png", "edp-thumbnail.png"]
    assert portal.connections == []


async def test_edp_picture_does_nothing_when_off_or_archived() -> None:
    for kwargs in (
        {"settings": AdminEdpSettings(id=1, enabled=False, pat="token")},
        {"item": _Item(archived=True)},
    ):
        worker, _, repo = _worker(**kwargs)  # type: ignore[arg-type]

        await worker.execute(EVENT)

        assert repo.pictures == {}, kwargs


async def test_edp_picture_does_nothing_without_storage() -> None:
    worker, portal, repo = _worker(with_storage=False)

    await worker.execute(EVENT)

    assert portal.connections == []
    assert repo.pictures == {}
