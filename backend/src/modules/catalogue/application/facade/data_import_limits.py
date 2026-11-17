"""
The row limit of a data import, from Catalogue's data import profiles.
"""

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.catalogue.domain.services.data_import_profiles import assert_row_count_within_limit
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType


async def assert_import_row_limit(
    settings_repo: ICatalogueSettingsRepository | None,
    import_type: DataImportType,
    row_count: int,
) -> None:
    """Refuses a batch with more rows than the import's profile allows. A
    use case built without the settings repository (the unit tests of row
    resolution) skips the check; every API path passes it."""
    if settings_repo is None:
        return
    settings = await settings_repo.get_data_import()
    assert_row_count_within_limit(import_type, settings.profile(import_type), row_count)
