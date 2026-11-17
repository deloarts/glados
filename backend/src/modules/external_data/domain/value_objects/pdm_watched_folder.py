"""One vault folder the PDM poller scans, stored as a JSON list on
AdminPdmSettings. The folder kinds, the documents-folder matching and the
role of `folder_id` are described in docs/PDM_INTEGRATION.md's watched
folder section."""

import re
from dataclasses import dataclass


def normalize_path(raw: str) -> str:
    """Normalizes a vault-relative path to single backslashes with one
    leading and no trailing separator. An empty input stays "", the root."""
    text = raw.strip().replace("/", "\\")
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    text = text.strip("\\")
    return f"\\{text}" if text else ""


@dataclass(frozen=True)
class PdmWatchedFolder:
    path: str  # vault-relative, normalized per normalize_path above
    kind: str  # "made" | "bought" | "by_kind" | "documents"
    recursive: bool
    enabled: bool
    # "documents" folders only.
    match_by: str | None = None  # "datacard" | "filename"
    filename_pattern: str | None = None
    # Survives renames, so the poller prefers it over `path`; None when the
    # folder was typed in by hand.
    folder_id: int | None = None


def validate_watched_folder(folder: PdmWatchedFolder) -> None:
    """A `documents` folder needs `match_by`, and a filename match needs a
    pattern with `part_number` and `revision` groups."""
    if folder.kind != "documents":
        return
    if folder.match_by not in ("datacard", "filename"):
        raise ValueError(
            f"watched folder {folder.path!r}: kind 'documents' requires match_by "
            "'datacard' or 'filename'."
        )
    if folder.match_by != "filename":
        return
    if not folder.filename_pattern:
        raise ValueError(
            f"watched folder {folder.path!r}: match_by 'filename' requires filename_pattern."
        )
    try:
        compiled = re.compile(folder.filename_pattern)
    except re.error as exc:
        raise ValueError(
            f"watched folder {folder.path!r}: filename_pattern does not compile: {exc}."
        ) from exc
    missing = {"part_number", "revision"} - set(compiled.groupindex)
    if missing:
        raise ValueError(
            f"watched folder {folder.path!r}: filename_pattern is missing named group(s) "
            f"{sorted(missing)}."
        )


def match_watched_folder(
    folders: list[PdmWatchedFolder], file_path: str
) -> PdmWatchedFolder | None:
    """The enabled folder with the longest path covering `file_path`,
    honoring `recursive`. Case-insensitive, because PDM path casing is not
    stable."""
    normalized = normalize_path(file_path).lower()
    best: PdmWatchedFolder | None = None
    for folder in folders:
        if not folder.enabled:
            continue
        # The trailing separator keeps \Parts from covering a sibling \Parts-Old.
        folder_path = normalize_path(folder.path).lower()
        if not normalized.startswith(folder_path + "\\"):
            continue
        remainder = normalized[len(folder_path) :].lstrip("\\")
        if not remainder:
            continue  # the folder itself, never a file
        if not folder.recursive and "\\" in remainder:
            continue  # file lives in a subfolder, this entry isn't recursive
        if best is None or len(folder.path) > len(best.path):
            best = folder
    return best
