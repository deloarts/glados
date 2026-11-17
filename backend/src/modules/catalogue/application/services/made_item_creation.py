"""
Shared validation + process-construction helpers behind CreateMadeItem and
CreateMadeItemRevision: a new revision is built through "the same
validation path as CreateMadeItem" (article groups, material-source
exclusivity, archived-method checks, processes incl. grouping), so that
logic lives here once instead of being copy-pasted between the two use
cases. Application layer (not
domain): it takes repository ports as parameters, which domain code may
not depend on.
"""

from datetime import datetime
from typing import Protocol

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import assert_valid_step_role
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.domain.value_objects.step_role import StepRole
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
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


async def assert_material_source_valid(
    bought_item_id: int | None,
    source_item_id: int | None,
    article_group_ids: list[int],
    article_group_repo: IArticleGroupRepository,
    bought_item_repo: IBoughtItemRepository,
    source_item_repo: ISourceItemRepository,
) -> None:
    """The article-group / material-source-exclusivity checks CreateMadeItem
    and CreateMadeItemRevision both run before touching the database."""
    MadeItemCatalogueRules.assert_at_most_one_material_source(bought_item_id, source_item_id)

    if article_group_ids:
        found = await article_group_repo.get_by_ids(article_group_ids)
        if len(found) != len(set(article_group_ids)):
            missing = set(article_group_ids) - {g.id for g in found}
            raise ArticleGroupNotFoundError(f"Article group(s) {missing} not found.")

    if bought_item_id is not None:
        bought_item = found_or_raise(
            await bought_item_repo.get_by_id(bought_item_id),
            BoughtItemNotFoundError,
            f"Bought item #{bought_item_id} not found.",
        )
        BoughtItemCatalogueRules.assert_item_active(bought_item)

    if source_item_id is not None:
        source_item = found_or_raise(
            await source_item_repo.get_by_id(source_item_id),
            SourceItemNotFoundError,
            f"Source item #{source_item_id} not found.",
        )
        SourceItemCatalogueRules.assert_item_active(source_item)


async def assert_customer_data_valid(
    actor: User,
    customer_id: int | None,
    customer_part_number: str | None,
    customer_revision: str | None,
    customer_repo: ICustomerRepository,
) -> None:
    """The customer-data checks of a web or `pat` write: the data is
    complete and the customer exists, archived or not. PDM ingest, as the
    system user, is exempt, because it stores what the datacard holds and
    already resolved a dangling customer reference to None."""
    if actor.is_systemuser:
        return
    MadeItemCatalogueRules.assert_customer_data_complete(
        customer_id, customer_part_number, customer_revision
    )
    if customer_id is not None:
        found_or_raise(
            await customer_repo.get_by_id(customer_id),
            CustomerNotFoundError,
            f"Customer #{customer_id} not found.",
        )


async def validate_processes(
    processes: list[CreateMadeItemProcessCommand],
    fabrication_method_repo: IFabricationMethodRepository,
    inspection_method_repo: IInspectionMethodRepository,
) -> dict[int, InspectionMethod]:
    """Role-shape and method existence/archived checks for every staged
    process. Returns the inspection methods keyed by id so
    build_and_save_processes can seed each inspection process's default
    durations without re-querying."""
    inspection_methods_by_id: dict[int, InspectionMethod] = {}
    for process_cmd in processes:
        assert_valid_step_role(
            process_cmd.role,
            process_cmd.fabrication_method_id,
            process_cmd.inspection_method_id,
        )
        if process_cmd.role == StepRole.FABRICATION:
            assert process_cmd.fabrication_method_id is not None  # assert_valid_step_role above
            method = await fabrication_method_repo.get_by_id(process_cmd.fabrication_method_id)
            if not method:
                raise FabricationMethodNotFoundError(
                    f"Fabrication method #{process_cmd.fabrication_method_id} not found."
                )
            if method.archived:
                raise FabricationMethodArchivedError(
                    f"Fabrication method #{process_cmd.fabrication_method_id} is archived."
                )
        else:
            assert process_cmd.inspection_method_id is not None  # assert_valid_step_role above
            inspection_method = await inspection_method_repo.get_by_id(
                process_cmd.inspection_method_id
            )
            if not inspection_method:
                raise InspectionMethodNotFoundError(
                    f"Inspection method #{process_cmd.inspection_method_id} not found."
                )
            if inspection_method.archived:
                raise InspectionMethodArchivedError(
                    f"Inspection method #{process_cmd.inspection_method_id} is archived."
                )
            inspection_methods_by_id[process_cmd.inspection_method_id] = inspection_method
    return inspection_methods_by_id


def _resolve_staged_group_indexes(processes: list[CreateMadeItemProcessCommand]) -> list[int]:
    """Normalizes the staged routing's optional group_index hints into
    contiguous 0-based indexes: a None value always starts its own new
    group; consecutive equal non-None values merge into one group. Never
    trusts the raw client values as final indexes, so a malformed payload
    (gaps, non-contiguous repeats) degrades gracefully instead of
    erroring."""
    result: list[int] = []
    next_index = -1
    prev_raw: object = object()
    for process_cmd in processes:
        raw = process_cmd.group_index
        if raw is None or raw != prev_raw:
            next_index += 1
        result.append(next_index)
        prev_raw = raw
    return result


def _assert_no_mixed_inspection_group(
    processes: list[CreateMadeItemProcessCommand], group_indexes: list[int]
) -> None:
    """Mirrors made_item_rules.validate_process_grouping's singleton rule
    for the staged (nested-process) creation path, which builds its own
    group_indexes from client hints instead of going through that
    validator directly (there are no persisted process ids yet to key
    groups by)."""
    by_group: dict[int, list[CreateMadeItemProcessCommand]] = {}
    for process_cmd, group_index in zip(processes, group_indexes, strict=True):
        by_group.setdefault(group_index, []).append(process_cmd)
    for group_index, group in by_group.items():
        if len(group) > 1 and any(p.role == StepRole.INSPECTION for p in group):
            raise MadeItemProcessGroupingInvalidError(
                f"Group {group_index} mixes an inspection step with another step; "
                "an inspection step must be its own group."
            )


class _ProcessStore(Protocol):
    """What building the processes writes; the made item repository and
    CAD & external data's made item store both satisfy it."""

    async def save_process(self, process: MadeItemProcess) -> MadeItemProcess: ...


async def build_and_save_processes(
    made_item_repo: _ProcessStore,
    made_item_id: int,
    processes: list[CreateMadeItemProcessCommand],
    inspection_methods_by_id: dict[int, InspectionMethod],
    creator_id: int,
    now: datetime,
) -> None:
    """Builds and save_process()s every staged process for a
    brand-new made item, resolving staged grouping the same way
    CreateMadeItem always has. Shared verbatim by CreateMadeItemRevision so
    "New revision" copies processes (incl. grouping) identically to a
    plain create."""
    group_indexes = _resolve_staged_group_indexes(processes)
    _assert_no_mixed_inspection_group(processes, group_indexes)
    for position, (process_cmd, group_index) in enumerate(
        zip(processes, group_indexes, strict=True)
    ):
        seed_method = (
            inspection_methods_by_id.get(process_cmd.inspection_method_id)
            if process_cmd.inspection_method_id is not None
            else None
        )
        setup_minutes, minutes_per_piece = (
            seed_inspection_estimates(
                seed_method,
                process_cmd.estimated_setup_minutes,
                process_cmd.estimated_minutes_per_piece,
            )
            if seed_method is not None
            else (process_cmd.estimated_setup_minutes, process_cmd.estimated_minutes_per_piece)
        )
        process = MadeItemProcess(
            id=0,
            created=now,
            note=process_cmd.note,
            estimated_setup_minutes=setup_minutes,
            estimated_minutes_per_piece=minutes_per_piece,
            creator_id=creator_id,
            fabrication_method_id=process_cmd.fabrication_method_id,
            made_item_id=made_item_id,
            position=position,
            group_index=group_index,
            role=process_cmd.role,
            inspection_method_id=process_cmd.inspection_method_id,
        )
        await made_item_repo.save_process(process)
