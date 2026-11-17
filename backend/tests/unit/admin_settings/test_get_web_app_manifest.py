import struct
from types import SimpleNamespace
from typing import Any

from src.modules.platform.application.use_cases.admin_settings.get_web_app_manifest import (
    GetWebAppManifest,
)


class FakeBrandingRepo:
    def __init__(self, favicon_key: str | None) -> None:
        self._favicon_key = favicon_key

    async def get_branding(self) -> Any:
        return SimpleNamespace(
            app_name="Werkstatt",
            app_description="Production planning",
            favicon_key=self._favicon_key,
        )


class FakeStorage:
    def __init__(self, objects: dict[str, tuple[bytes, str]]) -> None:
        self._objects = objects

    async def download(self, key: str) -> tuple[bytes, str]:
        return self._objects[key]


def _png(size: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", size, size)


async def test_the_manifest_carries_the_branding_name_and_description() -> None:
    result = await GetWebAppManifest(FakeBrandingRepo(None), None).execute()  # type: ignore[arg-type]

    assert result.name == "Werkstatt"
    assert result.description == "Production planning"
    assert result.favicon_type is None
    assert result.favicon_sizes is None


async def test_a_large_png_favicon_becomes_the_install_icon() -> None:
    storage = FakeStorage({"public/favicon.png": (_png(256), "image/png")})

    result = await GetWebAppManifest(FakeBrandingRepo("public/favicon.png"), storage).execute()  # type: ignore[arg-type]

    assert result.favicon_type == "image/png"
    assert result.favicon_sizes == "256x256"


async def test_a_small_favicon_leaves_the_glados_icon() -> None:
    storage = FakeStorage({"public/favicon.png": (_png(32), "image/png")})

    result = await GetWebAppManifest(FakeBrandingRepo("public/favicon.png"), storage).execute()  # type: ignore[arg-type]

    assert result.favicon_type is None
    assert result.favicon_sizes is None
