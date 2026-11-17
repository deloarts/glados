"""
Cold-folder poll cadence policy for the PDM poller (see PollPdmVault's
docstring and docs/reference/pdm-sync.md section 3.10): a watched folder with
no changes across consecutive scheduled runs is walked less often, backing
off exponentially up to an admin-configured cap. Pure functions only, no
framework imports, no I/O; PollPdmVault owns when to call these, what state to load and where to
persist the result.
"""

from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import normalize_path


def next_interval_minutes(
    base_minutes: int, consecutive_unchanged_runs: int, max_multiplier: int
) -> int:
    """The poll interval, in minutes, a watched folder should wait before
    its next scheduled walk, given how many scheduled runs in a row found
    it unchanged. Doubles per unchanged run (1x, 2x, 4x, ...) and is capped
    at `base_minutes * max_multiplier`. Zero unchanged runs naturally
    returns `base_minutes` (2**0 is 1), and a `max_multiplier` of 1 keeps
    every folder at the base interval regardless of streak length,
    effectively disabling backoff."""
    doubled = base_minutes * (1 << consecutive_unchanged_runs)
    return min(doubled, base_minutes * max_multiplier)


def folder_key(folder: PdmWatchedFolder) -> str:
    """The stable identity a watched folder's cadence state is keyed on:
    its resolved PDM folder id when the admin's picker set one (stable
    across a rename), else its own normalised, lower-cased path, so both
    identity modes share one string key regardless of which a given folder
    was configured with. Mirrors match_watched_folder's own
    case-insensitive path comparison."""
    if folder.folder_id is not None:
        return f"id:{folder.folder_id}"
    return f"path:{normalize_path(folder.path).lower()}"
