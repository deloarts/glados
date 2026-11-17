"""
Keeps the read scenarios complete. Every repository class must have a
scenario in one of this package's `test_*` modules, be relationship free
(verified against the ORM metadata), be a generic base exercised through its
subclasses, or be listed as a known gap.
"""

import importlib
import inspect
import itertools
import pkgutil
import sys
from types import ModuleType

from sqlalchemy import inspect as sa_inspect

import tests.integration.repository_reads as package
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.catalogue_settings_repository import (
    SqlAlchemyCatalogueSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.external_data_settings_repository import (
    SqlAlchemyExternalDataSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_document_link_repository import (
    SqlAlchemyPdmDocumentLinkRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_folder_poll_state_repository import (
    SqlAlchemyPdmFolderPollStateRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_reconciliation_finding_repository import (
    SqlAlchemyPdmReconciliationFindingRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_usage_repository import (
    SqlAlchemyBoughtItemUsages,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.fulfillment_settings_repository import (
    SqlAlchemyFulfillmentSettingsRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_usage_repository import (
    SqlAlchemyMadeItemUsages,
)
from src.modules.operations.adapters.outbound.persistence.repositories.operations_settings_repository import (
    SqlAlchemyOperationsSettingsRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.time_tracking_credentials_repository import (
    SqlAlchemyUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories.agent_call_repository import (
    SqlAlchemyAgentCallRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.agent_consent_repository import (
    SqlAlchemyAgentConsentRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_usage_log_repository import (
    SqlAlchemyApiKeyUsageLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.backup_run_repository import (
    SqlAlchemyBackupRunRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.idempotency_key_repository import (
    SqlAlchemyIdempotencyKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.log_repository import (
    SqlAlchemyLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.passkey_repository import (
    SqlAlchemyPasskeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_usage_log_repository import (
    SqlAlchemyPatUsageLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.trusted_device_repository import (
    SqlAlchemyTrustedDeviceRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_pdm_link_repository import (
    SqlAlchemyUserPdmLinkRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_session_repository import (
    SqlAlchemyUserSessionRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.production_kpi_repository import (
    SqlAlchemyProductionKpiRepository,
)
from tests.integration.repository_reads._harness import READ_PREFIXES
from tests.integration.repository_reads._harness import WRITE_PREFIXES
from tests.integration.repository_reads._harness import Scenarios
from tests.integration.repository_reads._harness import public_async_methods
from tests.integration.repository_reads._harness import read_methods
from tests.layer_packages import layer_module_names

# Repositories whose models declare no relationships at all, so there is
# nothing a load option could miss. `test_relationship_free_exemptions_hold`
# re-checks the claim against the ORM metadata, so an entry fails the suite
# the day one of these models gains a relationship.
RELATIONSHIP_FREE_REPOSITORIES: set[type] = {
    SqlAlchemyAgentCallRepository,
    SqlAlchemyAgentConsentRepository,
    SqlAlchemyCatalogueSettingsRepository,
    SqlAlchemyExternalDataSettingsRepository,
    SqlAlchemyFulfillmentSettingsRepository,
    SqlAlchemyOperationsSettingsRepository,
    SqlAlchemyPlatformSettingsRepository,
    SqlAlchemyApiKeyRepository,
    SqlAlchemyApiKeyUsageLogRepository,
    SqlAlchemyBackupRunRepository,
    SqlAlchemyIdempotencyKeyRepository,
    SqlAlchemyLogRepository,
    SqlAlchemyPasskeyRepository,
    SqlAlchemyPatRepository,
    SqlAlchemyPatUsageLogRepository,
    SqlAlchemyPdmDocumentLinkRepository,
    SqlAlchemyPdmFileSnapshotRepository,
    SqlAlchemyPdmFolderPollStateRepository,
    SqlAlchemyPdmReconciliationFindingRepository,
    SqlAlchemyPdmSyncRunRepository,
    SqlAlchemyTrustedDeviceRepository,
    SqlAlchemyUserPdmLinkRepository,
    SqlAlchemyUserSessionRepository,
    SqlAlchemyUserTimeTrackingCredentialsRepository,
    SqlAlchemyWebhookDeliveryRepository,
    SqlAlchemyWebhookSubscriptionRepository,
}

# Repositories with no read method at all, only writes, so there is no load
# option to check. `test_write_only_exemptions_hold` re-checks the claim.
WRITE_ONLY_REPOSITORIES: set[type] = {
    SqlAlchemyBoughtItemUsages,
    SqlAlchemyMadeItemUsages,
}

# Repositories assembled from the module stores listed above, adding no
# query of their own.
ASSEMBLED_REPOSITORIES: set[type] = {
    SqlAlchemyAdminSettingsRepository,
}

# Generic bases that are never instantiated on their own; their queries run
# through the scenarios of the concrete subclasses.
GENERIC_BASES: set[type] = set()

# Repositories without a scenario yet. Each entry is a gap, not a decision:
# write the scenario and remove the line.
UNCOVERED_REPOSITORIES: dict[type, str] = {
    SqlAlchemyProductionKpiRepository: "not yet covered",
}


def _repository_classes() -> set[type]:
    found: set[type] = set()
    for module_name in layer_module_names("adapters/outbound/persistence/repositories"):
        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ and name.startswith("SqlAlchemy"):
                found.add(obj)
    return found


def _scenario_modules() -> list[ModuleType]:
    return [
        importlib.import_module(f"{package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(package.__path__)
        if info.name.startswith("test_") and info.name != "test_coverage"
    ]


def _covered() -> set[type]:
    covered: set[type] = set()
    for module in _scenario_modules():
        registry = module.SCENARIOS
        assert isinstance(registry, Scenarios)
        overlap = covered & set(registry.scenarios)
        assert not overlap, f"covered twice: {sorted(c.__name__ for c in overlap)}"
        covered |= set(registry.scenarios)
    return covered


def test_every_repository_is_covered_or_exempt() -> None:
    groups = [
        _covered(),
        RELATIONSHIP_FREE_REPOSITORIES,
        ASSEMBLED_REPOSITORIES,
        WRITE_ONLY_REPOSITORIES,
        GENERIC_BASES,
        set(UNCOVERED_REPOSITORIES),
    ]
    for a, b in itertools.combinations(groups, 2):
        assert not a & b, f"listed twice: {sorted(c.__name__ for c in a & b)}"
    listed = set().union(*groups)
    classes = _repository_classes()
    unknown = classes - listed
    assert not unknown, (
        f"repositories without a read scenario: {sorted(c.__name__ for c in unknown)}"
    )
    stale = listed - classes
    assert not stale, f"entries for classes that no longer exist: {stale}"


def test_every_public_method_is_classified() -> None:
    unclassified = {
        f"{cls.__name__}.{name}"
        for cls in _repository_classes()
        for name in public_async_methods(cls)
        if not name.startswith(READ_PREFIXES + WRITE_PREFIXES)
    }
    assert not unclassified, (
        f"name matches neither READ_PREFIXES nor WRITE_PREFIXES: {sorted(unclassified)}"
    )


def test_relationship_free_exemptions_hold() -> None:
    """Every ORM model a relationship-free repository module refers to
    must still declare no relationships."""
    for repo_cls in RELATIONSHIP_FREE_REPOSITORIES:
        module = sys.modules[repo_cls.__module__]
        models = [
            obj
            for obj in vars(module).values()
            if isinstance(obj, type) and issubclass(obj, Base) and obj is not Base
        ]
        assert models, f"{repo_cls.__name__} refers to no ORM model, check the exemption"
        for model in models:
            relationships = sa_inspect(model).relationships
            assert not relationships, (
                f"{model.__name__} (used by {repo_cls.__name__}) now has relationships "
                f"{sorted(relationships.keys())}; give the repository a scenario"
            )


def test_write_only_exemptions_hold() -> None:
    """A write-only repository must still have no read method."""
    for repo_cls in WRITE_ONLY_REPOSITORIES:
        assert not read_methods(repo_cls), (
            f"{repo_cls.__name__} now reads ({sorted(read_methods(repo_cls))}); give it a scenario"
        )
