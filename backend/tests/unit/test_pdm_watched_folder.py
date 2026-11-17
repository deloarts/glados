"""
Unit tests for match_watched_folder, the path match the trigger path, the
pre-release validation and the PDM settings save use to decide which watched
folder covers a file.
"""

from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import match_watched_folder


def _folder(path: str, *, recursive: bool = True, enabled: bool = True) -> PdmWatchedFolder:
    return PdmWatchedFolder(path=path, kind="made", recursive=recursive, enabled=enabled)


class TestMatchWatchedFolder:
    def test_file_directly_in_the_folder_matches(self):
        folder = _folder("\\Parts")
        assert match_watched_folder([folder], "\\Parts\\a.sldprt") is folder

    def test_sibling_folder_sharing_the_prefix_does_not_match(self):
        assert match_watched_folder([_folder("\\Parts")], "\\Parts-Old\\a.sldprt") is None

    def test_match_ignores_case(self):
        folder = _folder("\\Parts")
        assert match_watched_folder([folder], "\\PARTS\\a.sldprt") is folder

    def test_non_recursive_folder_skips_subfolders(self):
        assert (
            match_watched_folder([_folder("\\Parts", recursive=False)], "\\Parts\\Sub\\a.sldprt")
            is None
        )

    def test_disabled_folder_never_matches(self):
        assert (
            match_watched_folder([_folder("\\Parts", enabled=False)], "\\Parts\\a.sldprt") is None
        )

    def test_deepest_covering_folder_wins(self):
        outer = _folder("\\Parts")
        inner = _folder("\\Parts\\Bought")
        assert match_watched_folder([outer, inner], "\\Parts\\Bought\\a.sldprt") is inner

    def test_vault_root_covers_every_file(self):
        root = _folder("")
        assert match_watched_folder([root], "\\Parts\\a.sldprt") is root
