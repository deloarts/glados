"""
Unit tests for domain.services.pdm_poll_cadence: next_interval_minutes (the
exponential-backoff formula) and folder_key (the identity a watched
folder's cadence state is keyed on). No database, no HTTP.
"""

from src.modules.external_data.domain.services.pdm_poll_cadence import folder_key
from src.modules.external_data.domain.services.pdm_poll_cadence import next_interval_minutes
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder


class TestNextIntervalMinutes:
    def test_zero_unchanged_runs_gives_the_base_interval(self) -> None:
        assert next_interval_minutes(15, 0, 8) == 15

    def test_doubles_per_unchanged_run(self) -> None:
        assert next_interval_minutes(15, 1, 8) == 30
        assert next_interval_minutes(15, 2, 8) == 60

    def test_capped_at_base_times_max_multiplier(self) -> None:
        # 15 * 2**3 == 120 == 15 * 8, right at the cap.
        assert next_interval_minutes(15, 3, 8) == 120
        # 15 * 2**4 == 240, above the cap, clamped back to 120.
        assert next_interval_minutes(15, 4, 8) == 120
        assert next_interval_minutes(15, 10, 8) == 120

    def test_multiplier_one_always_returns_the_base_interval(self) -> None:
        assert next_interval_minutes(15, 0, 1) == 15
        assert next_interval_minutes(15, 1, 1) == 15
        assert next_interval_minutes(15, 5, 1) == 15


class TestFolderKey:
    def test_folder_id_mode_keys_by_id(self) -> None:
        folder = PdmWatchedFolder(
            path="\\Made-Parts", kind="made", recursive=True, enabled=True, folder_id=42
        )
        assert folder_key(folder) == "id:42"

    def test_path_mode_keys_by_normalised_lower_cased_path(self) -> None:
        folder = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
        assert folder_key(folder) == "path:\\made-parts"

    def test_folder_id_takes_precedence_over_path(self) -> None:
        folder = PdmWatchedFolder(
            path="\\Made-Parts",
            kind="made",
            recursive=True,
            enabled=True,
            folder_id=7,
        )
        assert folder_key(folder) == "id:7"

    def test_two_folders_with_the_same_path_case_share_a_key(self) -> None:
        lower = PdmWatchedFolder(path="\\parts", kind="made", recursive=True, enabled=True)
        upper = PdmWatchedFolder(path="\\PARTS", kind="made", recursive=True, enabled=True)
        assert folder_key(lower) == folder_key(upper)
