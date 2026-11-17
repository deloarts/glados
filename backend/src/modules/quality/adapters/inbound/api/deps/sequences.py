"""Use case factories: flow sequences of a product."""

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.adapters.inbound.api.deps.controlled_documents import (
    build_controlled_document_deps,
)
from src.modules.quality.adapters.inbound.api.deps.repositories import get_sequence_repo
from src.modules.quality.application.use_cases.sequence.delete_sequence import DeleteSequence
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequence
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceByPublicId
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceNames
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequenceRevisions
from src.modules.quality.application.use_cases.sequence.get_sequences import GetSequences
from src.modules.quality.application.use_cases.sequence.lock_sequence import LockSequence
from src.modules.quality.application.use_cases.sequence.lock_sequence import UnlockSequence
from src.modules.quality.application.use_cases.sequence.release_sequence import MarkSequenceInvalid
from src.modules.quality.application.use_cases.sequence.release_sequence import ReleaseSequence
from src.modules.quality.application.use_cases.sequence.revise_sequence import ReviseSequence
from src.modules.quality.application.use_cases.sequence.save_sequence import CreateSequence
from src.modules.quality.application.use_cases.sequence.save_sequence import UpdateSequence
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_product_device_kind_repo,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_device_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_variant_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceKindQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductVariantQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries

DEPS = build_controlled_document_deps(
    get_sequence_repo,
    get_many_cls=GetSequences,
    get_one_cls=GetSequence,
    get_revisions_cls=GetSequenceRevisions,
    get_by_public_id_cls=GetSequenceByPublicId,
    revise_cls=ReviseSequence,
    mark_invalid_cls=MarkSequenceInvalid,
    delete_cls=DeleteSequence,
    lock_cls=LockSequence,
    unlock_cls=UnlockSequence,
)

get_sequences_use_case = DEPS.get_many
get_sequence_use_case = DEPS.get_one
get_sequence_revisions_use_case = DEPS.get_revisions
get_sequence_by_public_id_use_case = DEPS.get_by_public_id


# Create, update and release check the content against the product's
# devices, kinds and variants, so they take the repositories the shared
# factories do not provide.
def get_create_sequence_use_case(
    repo: ISequenceRepository = Depends(get_sequence_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    product_repo: IProductQueries = Depends(get_product_repo),
    admin_settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    kind_repo: IProductDeviceKindQueries = Depends(get_product_device_kind_repo),
    variant_repo: IProductVariantQueries = Depends(get_product_variant_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateSequence:
    return CreateSequence(
        repo,
        project_repo=project_repo,
        product_repo=product_repo,
        admin_settings_repo=admin_settings_repo,
        device_repo=device_repo,
        kind_repo=kind_repo,
        variant_repo=variant_repo,
        uow=uow,
    )


def get_update_sequence_use_case(
    repo: ISequenceRepository = Depends(get_sequence_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    kind_repo: IProductDeviceKindQueries = Depends(get_product_device_kind_repo),
    variant_repo: IProductVariantQueries = Depends(get_product_variant_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateSequence:
    return UpdateSequence(
        repo, device_repo=device_repo, kind_repo=kind_repo, variant_repo=variant_repo, uow=uow
    )


def get_release_sequence_use_case(
    repo: ISequenceRepository = Depends(get_sequence_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    kind_repo: IProductDeviceKindQueries = Depends(get_product_device_kind_repo),
    variant_repo: IProductVariantQueries = Depends(get_product_variant_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ReleaseSequence:
    return ReleaseSequence(
        repo, device_repo=device_repo, kind_repo=kind_repo, variant_repo=variant_repo, uow=uow
    )


def get_sequence_names_use_case(
    repo: ISequenceRepository = Depends(get_sequence_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    kind_repo: IProductDeviceKindQueries = Depends(get_product_device_kind_repo),
    variant_repo: IProductVariantQueries = Depends(get_product_variant_repo),
) -> GetSequenceNames:
    return GetSequenceNames(
        repo, device_repo=device_repo, kind_repo=kind_repo, variant_repo=variant_repo
    )


get_revise_sequence_use_case = DEPS.revise
get_mark_sequence_invalid_use_case = DEPS.mark_invalid
get_delete_sequence_use_case = DEPS.delete
get_lock_sequence_use_case = DEPS.lock
get_unlock_sequence_use_case = DEPS.unlock
