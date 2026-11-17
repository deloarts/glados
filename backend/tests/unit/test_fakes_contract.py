"""
Guards the fakes in every `tests/**/fakes.py` module against drifting from
the ports they stand in for.

Each fake is mapped to its port explicitly in `CONTRACTS`. For every port
method the fake defines, the test checks that the fake is async exactly
when the port is, and that it accepts every parameter the port declares
under the same name, positional parameters in the port's order and
keyword-only parameters as keywords. The fake may add parameters of its
own if they have defaults, and it may give a port parameter a default the
port does not have, but it must keep a default the port has. A fake that
covers the whole port must define every port method; a fake that stands in
for only the part of a port its tests reach is marked `partial`. A public
method the port does not declare fails the test unless the mapping names it
as a test helper, because a method the port dropped is dead code that hides
the drift.

A second test makes sure every class in a fakes module has an entry, so a
new fake cannot skip the check.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Generic
from typing import Protocol

import pytest

from src.modules.catalogue.ports.outbound.bought_item_usage_port import IBoughtItemUsages
from src.modules.catalogue.ports.outbound.made_item_usage_port import IMadeItemUsages
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_file_repository import (
    IMadeItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.part_number_registry import (
    IPartNumberRegistry,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.stock_service_port import IStockService
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import ITimeTrackingProvider
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.ports.outbound.backup_jobs_port import IBackupJobs
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository
from tests.integration import fakes as integration_fakes
from tests.unit import fakes as shared_fakes
from tests.unit.admin_settings import fakes as admin_settings_fakes
from tests.unit.auto_plan import fakes as auto_plan_fakes
from tests.unit.ingest_pdm_file import fakes as ingest_fakes
from tests.unit.made_item import fakes as made_item_fakes
from tests.unit.production_lot import fakes as lot_fakes
from tests.unit.production_order import fakes as order_fakes
from tests.unit.stock_service import fakes as stock_service_fakes
from tests.unit.time_tracking import fakes as time_tracking_fakes

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _TESTS_ROOT.parent


@dataclass(frozen=True)
class Contract:
    """One fake and the port, or ports, it stands in for. A fake passed
    where several ports are expected lists all of them, and each method it
    defines is checked against every listed port that declares it.
    `helpers` names the public test-only methods the port does not
    declare, such as seeders and inspection helpers."""

    fake: type
    ports: tuple[type, ...]
    partial: bool = False
    helpers: frozenset[str] = field(default_factory=frozenset)


def _contract(
    fake: type, *ports: type, partial: bool = False, helpers: tuple[str, ...] = ()
) -> Contract:
    return Contract(fake=fake, ports=ports, partial=partial, helpers=frozenset(helpers))


CONTRACTS: list[Contract] = [
    # tests/unit/fakes.py
    _contract(shared_fakes.FakeUnitOfWork, IUnitOfWork),
    _contract(shared_fakes.FakeEventBus, IEventBus),
    _contract(shared_fakes.FakeBoughtItemUsages, IBoughtItemUsages),
    _contract(shared_fakes.FakeMadeItemUsages, IMadeItemUsages),
    # tests/integration/fakes.py
    _contract(
        integration_fakes.FakeLoginAttemptTracker,
        ILoginAttemptTracker,
        helpers=("expire", "is_locked"),
    ),
    _contract(integration_fakes.FakeReplayGuard, IReplayGuard, helpers=("expire",)),
    _contract(integration_fakes.FakeBackupJobs, IBackupJobs),
    # tests/unit/admin_settings/fakes.py
    _contract(
        admin_settings_fakes.FakeAdminSettingsRepository, IAdminSettingsRepository, partial=True
    ),
    _contract(
        admin_settings_fakes.FakePdmFileSnapshotRepository,
        IPdmFileSnapshotRepository,
        partial=True,
    ),
    _contract(
        admin_settings_fakes.FakeInspectionMethodRepository,
        IInspectionMethodRepository,
        partial=True,
    ),
    # tests/unit/auto_plan/fakes.py
    _contract(auto_plan_fakes.FakeOrderRepo, IProductionOrderRepository, partial=True),
    _contract(auto_plan_fakes.FakeLotRepo, IProductionLotRepository, partial=True),
    _contract(
        auto_plan_fakes.FakeEmptyRepo,
        IOrderItemRepository,
        ISourceItemDemandRepository,
        ISourceItemAllocationRepository,
        IMadeItemAllocationRepository,
        IMadeItemDemandItemRepository,
        IProductionMachineRepository,
        partial=True,
    ),
    _contract(auto_plan_fakes.FakeMachineRepo, IProductionMachineRepository, partial=True),
    _contract(auto_plan_fakes.FakePoolRepo, IMachinePoolRepository, partial=True),
    _contract(auto_plan_fakes.ClampingFakeMachineRepo, IProductionMachineRepository, partial=True),
    _contract(auto_plan_fakes.ClampingFakePoolRepo, IMachinePoolRepository, partial=True),
    _contract(auto_plan_fakes.FakeCalendarRepo, IMachineCalendarRepository, partial=True),
    _contract(auto_plan_fakes.FakeSettingsRepo, IAdminSettingsRepository, partial=True),
    # tests/unit/ingest_pdm_file/fakes.py
    _contract(ingest_fakes.FakeMadeItemRepository, IMadeItemRepository, partial=True),
    _contract(ingest_fakes.FakeBoughtItemRepository, IBoughtItemRepository, partial=True),
    _contract(ingest_fakes.FakeArticleGroupRepository, IArticleGroupRepository, partial=True),
    _contract(ingest_fakes.FakeSourceItemRepository, ISourceItemRepository, partial=True),
    _contract(ingest_fakes.FakeSupplierRepository, ISupplierRepository, partial=True),
    _contract(
        ingest_fakes.FakeFabricationMethodRepository, IFabricationMethodRepository, partial=True
    ),
    _contract(
        ingest_fakes.FakeInspectionMethodRepository, IInspectionMethodRepository, partial=True
    ),
    _contract(ingest_fakes.FakeAdminSettingsRepository, IAdminSettingsRepository, partial=True),
    _contract(ingest_fakes.FakePdmGateway, IPdmGateway, partial=True),
    _contract(ingest_fakes.FakePartNumberRegistry, IPartNumberRegistry, partial=True),
    _contract(ingest_fakes.FakePdmFileSnapshotRepository, IPdmFileSnapshotRepository, partial=True),
    _contract(ingest_fakes.FakeUserRepository, IUserRepository, partial=True),
    _contract(ingest_fakes.FakeUserPdmLinkRepository, IUserPdmLinkRepository, partial=True),
    # tests/unit/made_item/fakes.py
    _contract(made_item_fakes.FakeMadeItemRepository, IMadeItemRepository, partial=True),
    _contract(made_item_fakes.FakeMadeItemFileRepository, IMadeItemFileRepository, partial=True),
    _contract(made_item_fakes.FakeArticleGroupRepository, IArticleGroupRepository, partial=True),
    _contract(made_item_fakes.FakeSourceItemRepository, ISourceItemRepository, partial=True),
    _contract(made_item_fakes.FakeBoughtItemRepository, IBoughtItemRepository, partial=True),
    _contract(made_item_fakes.FakeCustomerRepository, ICustomerRepository, partial=True),
    _contract(
        made_item_fakes.FakeFabricationMethodRepository,
        IFabricationMethodRepository,
        partial=True,
    ),
    _contract(
        made_item_fakes.FakeInspectionMethodRepository,
        IInspectionMethodRepository,
        partial=True,
    ),
    _contract(made_item_fakes.FakeAdminSettingsRepository, IAdminSettingsRepository, partial=True),
    _contract(made_item_fakes.FakePartNumberRegistry, IPartNumberRegistry, partial=True),
    # tests/unit/production_lot/fakes.py
    _contract(lot_fakes.FakeProductionLotRepository, IProductionLotRepository, partial=True),
    _contract(lot_fakes.FakeMadeItemRepository, IMadeItemRepository, partial=True),
    _contract(lot_fakes.FakeMadeItemDemandRepository, IMadeItemDemandItemRepository, partial=True),
    _contract(lot_fakes.FakeMadeItemAllocationRepository, IMadeItemAllocationRepository),
    _contract(lot_fakes.FakeAdminSettingsRepository, IAdminSettingsRepository, partial=True),
    _contract(lot_fakes.FakeInspectionMethodRepository, IInspectionMethodRepository, partial=True),
    _contract(
        lot_fakes.FakeProductionMachineRepository, IProductionMachineRepository, partial=True
    ),
    _contract(
        lot_fakes.FakeFabricationMethodRepository, IFabricationMethodRepository, partial=True
    ),
    _contract(lot_fakes.FakeOrderRepository, IOrderRepository, partial=True),
    _contract(lot_fakes.FakeOrderItemRepository, IOrderItemRepository, partial=True),
    _contract(
        lot_fakes.FakeOrderItemDeliveryRepository, IOrderItemDeliveryRepository, partial=True
    ),
    _contract(
        lot_fakes.FakeBoughtItemAllocationRepository,
        IBoughtItemAllocationRepository,
        partial=True,
    ),
    _contract(
        lot_fakes.FakeBoughtItemDemandRepository, IBoughtItemDemandItemRepository, partial=True
    ),
    _contract(lot_fakes.FakeProductionOrderRepository, IProductionOrderRepository, partial=True),
    _contract(lot_fakes.FakeEventBus, IEventBus),
    _contract(lot_fakes.FakeUnitOfWork, IUnitOfWork),
    _contract(lot_fakes.FakeBoughtItemRepository, IBoughtItemRepository, partial=True),
    _contract(lot_fakes.FakeSourceItemRepository, ISourceItemRepository, partial=True),
    _contract(lot_fakes.FakeSourceItemDemandRepository, ISourceItemDemandRepository, partial=True),
    _contract(
        lot_fakes.FakeSourceItemAllocationRepository,
        ISourceItemAllocationRepository,
        partial=True,
    ),
    _contract(lot_fakes.FakeRecomputeMachineSchedule, ScheduleRecompute),
    _contract(lot_fakes.FakeProjectRepository, IProjectRepository, partial=True),
    # tests/unit/production_order/fakes.py
    _contract(order_fakes.FakeProductionLotRepository, IProductionLotRepository, partial=True),
    _contract(
        order_fakes.FakeProductionMachineRepository, IProductionMachineRepository, partial=True
    ),
    _contract(order_fakes.FakeProductionOrderRepository, IProductionOrderRepository, partial=True),
    _contract(order_fakes.FakeProductionOrderFileRepository, IProductionOrderFileRepository),
    _contract(order_fakes.FakeLockPlan, LockPlan, partial=True),
    _contract(order_fakes.FakeAdminSettingsRepository, IAdminSettingsRepository, partial=True),
    _contract(order_fakes.FakeRecomputeSchedule, ScheduleRecompute),
    _contract(order_fakes.FakeEventBus, IEventBus),
    _contract(order_fakes._UnusedLineAllocations, ISourceItemAllocationRepository, partial=True),
    _contract(order_fakes.FakeUnitOfWork, IUnitOfWork),
    _contract(order_fakes.FakeMachinePoolRepository, IMachinePoolRepository, partial=True),
    _contract(
        order_fakes.FakeProductionOrderInterruptionRepository,
        IProductionOrderInterruptionRepository,
    ),
    # tests/unit/stock_service/fakes.py
    _contract(stock_service_fakes.FakeStockService, IStockService, helpers=("factory",)),
    # tests/unit/time_tracking/fakes.py
    _contract(time_tracking_fakes.FakeSettingsRepo, IAdminSettingsRepository, partial=True),
    _contract(time_tracking_fakes.FakeCredentialsRepo, IUserTimeTrackingCredentialsRepository),
    _contract(time_tracking_fakes.FakeTracker, ILoginAttemptTracker),
    _contract(
        time_tracking_fakes.FakeProvider, ITimeTrackingProvider, helpers=("factory", "names")
    ),
    _contract(time_tracking_fakes.FakeUserRepo, IUserRepository, partial=True),
]

# Classes in a fakes module that stand in for no single port, each with the
# reason it is left out of CONTRACTS.
NOT_PORT_FAKES: dict[type, str] = {
    made_item_fakes.FakeMadeItemFileStorage: "only has to be non-None, defines no methods",
    order_fakes._UnusedRepository: "answers every attribute with a coroutine that fails the test",
}


def _public_methods(cls: type, *, stop_at: tuple[type, ...]) -> dict[str, Any]:
    """The public functions `cls` defines or inherits, unwrapped from
    staticmethod and classmethod. Classes in `stop_at` contribute nothing."""
    methods: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        if klass in stop_at:
            continue
        for name, value in vars(klass).items():
            if name.startswith("_"):
                continue
            if isinstance(value, staticmethod | classmethod):
                value = value.__func__
            if inspect.isfunction(value):
                methods[name] = value
    return methods


def _port_methods(port: type) -> dict[str, Any]:
    return _public_methods(port, stop_at=(object, Protocol, Generic))


def _call_kind(function: Any) -> str:
    if inspect.isasyncgenfunction(function):
        return "an async generator"
    if inspect.iscoroutinefunction(function):
        return "async"
    return "sync"


_POSITIONAL = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
_VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)


def _signature_problems(port_name: str, name: str, port_fn: Any, fake_fn: Any) -> list[str]:
    """Every way in which `fake_fn` cannot be called the way the port
    declares `port_fn`."""
    where = f"{name} (against {port_name})"
    problems: list[str] = []
    if _call_kind(port_fn) != _call_kind(fake_fn):
        problems.append(
            f"{where}: the port method is {_call_kind(port_fn)}, the fake is {_call_kind(fake_fn)}"
        )

    port_params = list(inspect.signature(port_fn).parameters.values())[1:]
    fake_params = list(inspect.signature(fake_fn).parameters.values())[1:]
    fake_by_name = {p.name: p for p in fake_params}
    fake_positional = [p.name for p in fake_params if p.kind in _POSITIONAL]
    fake_kinds = {p.kind for p in fake_params}

    port_positional = [p for p in port_params if p.kind in _POSITIONAL]
    for index, param in enumerate(port_positional):
        found = fake_positional[index] if index < len(fake_positional) else None
        if found != param.name and inspect.Parameter.VAR_POSITIONAL not in fake_kinds:
            problems.append(
                f"{where}: positional parameter {index + 1} is {param.name!r} on the port, "
                f"{found!r} on the fake"
            )

    for param in port_params:
        fake_param = fake_by_name.get(param.name)
        if param.kind is inspect.Parameter.KEYWORD_ONLY and (
            fake_param is None or fake_param.kind not in (*_POSITIONAL[1:], param.kind)
        ):
            if inspect.Parameter.VAR_KEYWORD not in fake_kinds:
                problems.append(f"{where}: the fake lacks the keyword parameter {param.name!r}")
            continue
        if param.kind in _VARIADIC and param.kind not in fake_kinds:
            problems.append(f"{where}: the port accepts {param}, the fake does not")
            continue
        if (
            fake_param is not None
            and param.default is not inspect.Parameter.empty
            and fake_param.default is inspect.Parameter.empty
        ):
            problems.append(
                f"{where}: {param.name!r} has a default on the port but not on the fake"
            )

    port_names = {p.name for p in port_params}
    problems.extend(
        f"{where}: the fake requires {p.name!r}, which the port does not declare"
        for p in fake_params
        if p.name not in port_names
        and p.kind not in _VARIADIC
        and p.default is inspect.Parameter.empty
    )
    return problems


def _contract_problems(contract: Contract) -> list[str]:
    fake_methods = _public_methods(contract.fake, stop_at=(object,))
    declared: set[str] = set()
    problems: list[str] = []
    for port in contract.ports:
        port_methods = _port_methods(port)
        declared |= port_methods.keys()
        for name, port_fn in port_methods.items():
            fake_fn = fake_methods.get(name)
            if fake_fn is None:
                if not contract.partial:
                    problems.append(f"{name}: declared on {port.__name__}, missing on the fake")
                continue
            problems.extend(_signature_problems(port.__name__, name, port_fn, fake_fn))

    if contract.partial and len(contract.ports) == 1 and declared <= fake_methods.keys():
        problems.append("the fake implements the whole port, so it should not be marked partial")
    problems.extend(
        f"{name}: not declared on the port; delete it, or name it as a test helper"
        for name in sorted(fake_methods.keys() - declared - contract.helpers)
    )
    problems.extend(
        f"{name}: is declared on the port, so it is not a test helper"
        for name in sorted(contract.helpers & declared)
    )
    return problems


@pytest.mark.parametrize(
    "contract",
    CONTRACTS,
    ids=[f"{c.fake.__module__.removeprefix('tests.')}.{c.fake.__name__}" for c in CONTRACTS],
)
def test_fake_matches_its_port(contract: Contract) -> None:
    problems = _contract_problems(contract)
    assert not problems, "\n".join(problems)


def test_every_class_in_a_fakes_module_has_a_contract() -> None:
    covered = {c.fake for c in CONTRACTS} | NOT_PORT_FAKES.keys()
    unmapped: list[str] = []
    for path in sorted(_TESTS_ROOT.rglob("fakes.py")):
        module_name = ".".join(path.relative_to(_BACKEND_ROOT).with_suffix("").parts)
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if inspect.isclass(value) and value.__module__ == module_name and value not in covered:
                unmapped.append(f"{module_name}.{name}")
    assert not unmapped, "Map these fakes to their ports in CONTRACTS: " + ", ".join(unmapped)


def test_fake_unit_of_work_satisfies_port() -> None:
    assert isinstance(shared_fakes.FakeUnitOfWork(), IUnitOfWork)


def test_fake_event_bus_satisfies_port() -> None:
    assert isinstance(shared_fakes.FakeEventBus(), IEventBus)
