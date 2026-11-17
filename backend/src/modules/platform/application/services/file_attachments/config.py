"""Declares what differs between the file attachment families (labels,
storage prefix, errors, categories and their validation) as one
`ItemFileKind` per family, so the use cases themselves are shared. DTOs,
schemas and ports stay per family; the shared code relies on their
identical field names apart from `fk_field`.
"""

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar
from uuid import UUID

from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.content_types import SVG
from src.modules.platform.ports.outbound.storage_port import IStoragePort

MiB = 1024 * 1024

# What a browser can send as an image, the same for every family.
IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
# Accepted only for a family's svg_categories.
SVG_CONTENT_TYPE = SVG


class ItemFileCategory(Protocol):
    """What the shared code needs of a family's category enum."""

    @property
    def value(self) -> str: ...

    def is_singleton(self) -> bool: ...


class ItemFileEntity(Protocol):
    """The attributes of a file entity the shared code reads. `file_name` is
    writable, since a rename sets it; the family's FK field is read through
    `ItemFileKind.fk_field`."""

    file_name: str

    @property
    def id(self) -> int: ...
    @property
    def public_id(self) -> UUID: ...
    @property
    def stored_name(self) -> str: ...
    @property
    def mime_type(self) -> str: ...
    @property
    def size_bytes(self) -> int: ...
    @property
    def storage_path(self) -> str: ...
    @property
    def sha256(self) -> str: ...
    @property
    def category(self) -> ItemFileCategory: ...
    @property
    def created(self) -> datetime: ...
    @property
    def uploaded_by_user_id(self) -> int: ...


FileT = TypeVar("FileT", bound=ItemFileEntity)
ResultT = TypeVar("ResultT")
CategoryT = TypeVar("CategoryT", bound=ItemFileCategory)


@dataclass(frozen=True)
class ExtraCategoryValidator:
    """An extension-gated category such as STEP, MESH or DXF. Like every
    upload, its stored content type comes from the extension
    (content_types.py), whatever the browser sent."""

    extensions: frozenset[str]
    invalid_message: str  # .format(file_name=...)


STEP_VALIDATOR = ExtraCategoryValidator(
    extensions=frozenset({".step", ".stp"}),
    invalid_message="STEP files must have a .step or .stp extension (got {file_name!r}).",
)

# The MESH slot holds whichever mesh format was uploaded last, STL and 3MF
# describe the same geometry, so they share one singleton category rather
# than competing for two.
MESH_VALIDATOR = ExtraCategoryValidator(
    extensions=frozenset({".stl", ".3mf"}),
    invalid_message="Mesh files must have a .stl or .3mf extension (got {file_name!r}).",
)

DXF_VALIDATOR = ExtraCategoryValidator(
    extensions=frozenset({".dxf"}),
    invalid_message="DXF files must have a .dxf extension (got {file_name!r}).",
)


@dataclass(frozen=True)
class ItemFileKind(Generic[FileT, ResultT, CategoryT]):
    """One family's declared shape, generic over its file entity, its result
    DTO and its category enum. `assert_can_update` gates writes only;
    downloading needs the same access as listing."""

    item_label: str  # lowercase, e.g. "bought item"
    storage_prefix: str  # e.g. "bought_items/catalogue"
    fk_field: str  # e.g. "bought_item_id"
    entity_cls: Callable[..., FileT]
    result_cls: Callable[..., ResultT]
    image_categories: frozenset[CategoryT]
    max_bytes: Mapping[CategoryT, int]
    extra_validators: Mapping[CategoryT, ExtraCategoryValidator]
    # Per family, because made items name the category (DRAWING or PDF).
    pdf_fallback_message: str
    item_not_found_error: type[Exception]
    file_not_found_error: type[Exception]
    file_too_large_error: type[Exception]
    file_invalid_type_error: type[Exception]
    # The actor-only write gate. None for a family whose write rule needs
    # the parent entity (products): its use cases resolve the parent first
    # and apply that rule themselves instead of calling assert_can_update.
    write_rule: Callable[[User], None] | None
    # Image categories that also take SVG. An SVG is cleaned on upload
    # (svg_sanitizer.py) and stored as SVG instead of being turned into PNG.
    svg_categories: frozenset[CategoryT] = frozenset()

    def assert_can_update(self, actor: User) -> None:
        if self.write_rule is None:
            raise TypeError(f"{self.item_label} files declare no actor-only write rule.")
        self.write_rule(actor)

    def make_entity(self, *, item_id: int, **fields: Any) -> FileT:
        return self.entity_cls(id=0, **{self.fk_field: item_id}, **fields)

    def to_result(
        self,
        entity: FileT,
        storage: IStoragePort | None,
        url: str | None = None,
        *,
        from_pdm: bool = False,
    ) -> ResultT:
        """Builds the result. A caller that already has the URL passes it;
        otherwise it is resolved here, None without storage. Only listings
        set `from_pdm`, since uploads are never PDM documents."""
        if url is None and storage is not None:
            url = get_storage_url_best_effort(
                storage,
                entity.storage_path,
                context=f"{self.item_label} file #{entity.id}",
                file_name=entity.file_name,
            )
        return self.result_cls(
            id=entity.id,
            public_id=entity.public_id,
            file_name=entity.file_name,
            stored_name=entity.stored_name,
            mime_type=entity.mime_type,
            size_bytes=entity.size_bytes,
            storage_path=entity.storage_path,
            sha256=entity.sha256,
            category=entity.category,
            created=entity.created,
            uploaded_by_user_id=entity.uploaded_by_user_id,
            url=url,
            from_pdm=from_pdm,
            **{self.fk_field: getattr(entity, self.fk_field)},
        )

    def validate_upload(
        self, category: CategoryT, content_type: str, file_name: str, size: int
    ) -> str:
        """Validates an upload and returns its extension, from which the
        caller derives the stored content type."""
        limit = self.max_bytes[category]
        if size > limit:
            mb = limit // MiB
            raise self.file_too_large_error(
                f"{category.value} files must be ≤ {mb} MB (got {size} bytes)."
            )

        # Browsers often send an SVG without its type (Windows has no MIME
        # mapping for it), so the extension also counts; the cleaner checks
        # the content either way.
        if category in self.svg_categories and (
            content_type == SVG_CONTENT_TYPE or Path(file_name).suffix.lower() == ".svg"
        ):
            return ".svg"

        if category in self.image_categories:
            if content_type not in IMAGE_CONTENT_TYPES:
                raise self.file_invalid_type_error(
                    f"Expected an image (JPEG/PNG/WebP) for {category.value}, got {content_type!r}."
                )
            return IMAGE_CONTENT_TYPES[content_type]

        extra = self.extra_validators.get(category)
        if extra is not None:
            ext = Path(file_name).suffix.lower()
            if ext not in extra.extensions:
                raise self.file_invalid_type_error(
                    extra.invalid_message.format(file_name=file_name)
                )
            return ext

        if content_type != "application/pdf":
            raise self.file_invalid_type_error(
                self.pdf_fallback_message.format(category=category.value, content_type=content_type)
            )
        return ".pdf"
