"""Use case factories: customers and suppliers."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.application.use_cases.customer.archive_customer import ArchiveCustomer
from src.modules.catalogue.application.use_cases.customer.create_customer import CreateCustomer
from src.modules.catalogue.application.use_cases.customer.get_customer import GetCustomer
from src.modules.catalogue.application.use_cases.customer.get_customer import GetCustomers
from src.modules.catalogue.application.use_cases.customer.restore_customer import RestoreCustomer
from src.modules.catalogue.application.use_cases.customer.update_customer import UpdateCustomer
from src.modules.catalogue.application.use_cases.supplier.archive_supplier import ArchiveSupplier
from src.modules.catalogue.application.use_cases.supplier.create_supplier import CreateSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSuppliers
from src.modules.catalogue.application.use_cases.supplier.restore_supplier import RestoreSupplier
from src.modules.catalogue.application.use_cases.supplier.update_supplier import UpdateSupplier
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import get_schedule_recompute
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_create_customer_use_case(
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateCustomer:
    return CreateCustomer(customer_repo=customer_repo, uow=uow)


def get_update_customer_use_case(
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateCustomer:
    return UpdateCustomer(customer_repo=customer_repo, uow=uow)


def get_archive_customer_use_case(
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveCustomer:
    return ArchiveCustomer(customer_repo=customer_repo, uow=uow)


def get_restore_customer_use_case(
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreCustomer:
    return RestoreCustomer(customer_repo=customer_repo, uow=uow)


def get_customer_use_case(
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
) -> GetCustomer:
    return GetCustomer(customer_repo=customer_repo)


def get_customers_use_case(
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
) -> GetCustomers:
    return GetCustomers(customer_repo=customer_repo)


def get_create_supplier_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateSupplier:
    return CreateSupplier(supplier_repo=supplier_repo, uow=uow)


def get_update_supplier_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: ScheduleRecompute = Depends(get_schedule_recompute),
) -> UpdateSupplier:
    return UpdateSupplier(supplier_repo=supplier_repo, uow=uow, recompute_schedule=recompute)


def get_supplier_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
) -> GetSupplier:
    return GetSupplier(supplier_repo=supplier_repo)


def get_suppliers_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
) -> GetSuppliers:
    return GetSuppliers(supplier_repo=supplier_repo)


def get_archive_supplier_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveSupplier:
    return ArchiveSupplier(supplier_repo=supplier_repo, uow=uow)


def get_restore_supplier_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreSupplier:
    return RestoreSupplier(supplier_repo=supplier_repo, uow=uow)
