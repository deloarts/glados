"""
Rig bundles every fake plus a wired IngestPdmFile (and the three reused
create use cases, sharing the same fakes) for one test. Used by every
test module in this package.
"""

import copy
from typing import Any

from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.use_cases.pdm.ingest_pdm_file import IngestPdmFile
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmTransition
from src.modules.platform.domain.entities.user import User
from tests.unit.fakes import FakeEventBus
from tests.unit.ingest_pdm_file._helpers import make_supplier
from tests.unit.ingest_pdm_file._helpers import make_user
from tests.unit.ingest_pdm_file.fakes import FakeAdminSettingsRepository
from tests.unit.ingest_pdm_file.fakes import FakeArticleGroupRepository
from tests.unit.ingest_pdm_file.fakes import FakeBoughtItemRepository
from tests.unit.ingest_pdm_file.fakes import FakeFabricationMethodRepository
from tests.unit.ingest_pdm_file.fakes import FakeInspectionMethodRepository
from tests.unit.ingest_pdm_file.fakes import FakeMadeItemRepository
from tests.unit.ingest_pdm_file.fakes import FakePartNumberRegistry
from tests.unit.ingest_pdm_file.fakes import FakePdmFileSnapshotRepository
from tests.unit.ingest_pdm_file.fakes import FakePdmGateway
from tests.unit.ingest_pdm_file.fakes import FakeSourceItemRepository
from tests.unit.ingest_pdm_file.fakes import FakeSupplierRepository
from tests.unit.ingest_pdm_file.fakes import FakeUserPdmLinkRepository
from tests.unit.ingest_pdm_file.fakes import FakeUserRepository
from tests.unit.made_item.fakes import FakeCustomerRepository


class _SnapshottingUnitOfWork:
    """Fake IUnitOfWork with real commit/rollback semantics against the
    rig's own stateful fakes, instead of merely counting calls.

    Every write these fakes take (save, claim, upsert_many, ...)
    lands straight in the fake's own instance attributes, with nothing
    else in the rig to undo it, unlike a real Session, whose rollback()
    discards every pending change since the last commit. That mismatch
    let a rolled-back write survive in earlier versions of this rig, so a
    test working around it had to open a brand new Rig() to retry a
    failed ingest instead of reusing the one whose failure it had just
    observed.

    commit() takes a deep copy of every tracked fake's `__dict__`.
    rollback() restores the most recent such copy (or the state each fake
    was constructed with, if commit() was never called), discarding
    anything written since, matching what a real transaction rollback
    does to the rows a use case wrote but never committed."""

    def __init__(self, tracked: list[object]) -> None:
        self._tracked = tracked
        self.committed = False
        self.rolled_back = False
        self.commits = 0
        self.rollbacks = 0
        self._snapshots = self._snapshot()

    def _snapshot(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(vars(fake)) for fake in self._tracked]

    async def commit(self) -> None:
        self.committed = True
        self.commits += 1
        self._snapshots = self._snapshot()

    async def rollback(self) -> None:
        self.rolled_back = True
        self.rollbacks += 1
        for fake, snapshot in zip(self._tracked, self._snapshots, strict=True):
            fake.__dict__.clear()
            fake.__dict__.update(copy.deepcopy(snapshot))


class Rig:
    """Bundles every fake plus a wired IngestPdmFile (and the three reused
    create use cases, sharing the same fakes) for one test."""

    def __init__(
        self,
        *,
        made_items: list[MadeItem] | None = None,
        bought_items: list[BoughtItem] | None = None,
        article_groups: list[ArticleGroup] | None = None,
        source_items: list[SourceItem] | None = None,
        customers: list[Customer] | None = None,
        suppliers: list[Supplier] | None = None,
        pdm_settings: AdminPdmSettings | None = None,
        made_item_settings: AdminMadeItemSettings | None = None,
        order_settings: AdminOrderSettings | None = None,
        registry: FakePartNumberRegistry | None = None,
        extra_users: list[User] | None = None,
        pdm_links: dict[int, int] | None = None,
        pdm_transitions: list[PdmTransition] | None = None,
        pdm_transitions_error: Exception | None = None,
    ) -> None:
        self.made_item_repo = FakeMadeItemRepository(made_items)
        self.bought_item_repo = FakeBoughtItemRepository(bought_items)
        self.article_group_repo = FakeArticleGroupRepository(article_groups)
        self.source_item_repo = FakeSourceItemRepository(source_items)
        self.customer_repo = FakeCustomerRepository(customers)
        self.supplier_repo = FakeSupplierRepository(
            suppliers if suppliers is not None else [make_supplier(id=1)]
        )
        self.fabrication_method_repo = FakeFabricationMethodRepository()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.admin_settings_repo = FakeAdminSettingsRepository(
            made_items=made_item_settings, orders=order_settings, pdm=pdm_settings
        )
        self.snapshot_repo = FakePdmFileSnapshotRepository()
        self.system_user = make_user()
        self.user_repo = FakeUserRepository(self.system_user, extra_users=extra_users)
        self.user_pdm_link_repo = FakeUserPdmLinkRepository(pdm_links)
        self.registry = registry or FakePartNumberRegistry()
        self.bus = FakeEventBus()
        # Every fake a use case in this package writes to pre-commit, so a
        # rollback has something real to restore, see
        # _SnapshottingUnitOfWork's own docstring.
        self.uow = _SnapshottingUnitOfWork(
            [
                self.made_item_repo,
                self.bought_item_repo,
                self.registry,
                self.snapshot_repo,
                self.bus,
            ]
        )
        self.pdm_gateway = FakePdmGateway(
            transitions=pdm_transitions, transitions_error=pdm_transitions_error
        )
        self.pdm_session = PdmSessionService(
            repo=self.admin_settings_repo, gateway_factory=lambda connection: self.pdm_gateway
        )

        self.create_made_item = CreateMadeItem(
            self.made_item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=self.customer_repo,
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        self.create_made_item_revision = CreateMadeItemRevision(
            self.made_item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=self.customer_repo,
        )
        self.create_bought_item = CreateBoughtItem(
            self.bought_item_repo,
            self.supplier_repo,
            self.article_group_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            cad_source=PdmCadSource(self.admin_settings_repo),
        )

        self.use_case = IngestPdmFile(
            self.made_item_repo,
            self.bought_item_repo,
            self.article_group_repo,
            self.source_item_repo,
            self.supplier_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            self.snapshot_repo,
            self.user_repo,
            self.user_pdm_link_repo,
            create_made_item=self.create_made_item,
            create_made_item_revision=self.create_made_item_revision,
            create_bought_item=self.create_bought_item,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            session=self.pdm_session,
            customer_repo=self.customer_repo,
        )
