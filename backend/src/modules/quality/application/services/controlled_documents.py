"""
The document control steps that read or write more than one revision,
shared by the use cases of every controlled document. Permissions are
checked by the caller first; these only load the neighbouring revision,
apply services/document_control.py and save in the order the one latest
revision per lineage index needs. Committing is left to the caller.
"""

from collections.abc import Callable
from typing import TypeVar

from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.quality.domain.services import document_control
from src.modules.quality.ports.outbound.repositories.controlled_document_repository import (
    IControlledDocumentRepository,
)
from src.modules.workspace.domain.errors import ProductArchivedError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

D = TypeVar("D", bound=ControlledDocument)


async def predecessor_of(repo: IControlledDocumentRepository[D], document: D) -> D | None:
    """The revision directly before this one, or None for a first revision."""
    lineage = await repo.get_lineage(document.lineage)
    ids = [revision.id for revision in lineage]
    if document.id not in ids:
        return None
    index = ids.index(document.id)
    return lineage[index + 1] if index + 1 < len(lineage) else None


async def start_revision(
    repo: IControlledDocumentRepository[D],
    admin_settings: IFulfillmentSettingsRepository,
    current: D,
    actor: User,
    *,
    reason: str,
    takes_over_now: bool,
) -> D:
    """Saves the successor of `current` as the new latest revision, numbered
    in the scheme of the made item settings."""
    settings = await admin_settings.get_made_items()
    revision = revision_scheme.next_revision(
        current.revision, settings.revision_skip_ambiguous_letters
    )
    successor = document_control.start_revision(
        current,
        actor,
        now_utc(),
        revision=revision,
        reason=reason.strip(),
        takes_over_now=takes_over_now,
    )
    # The previous revision gives up being the latest before the new one
    # claims it.
    await repo.save(current)
    return await repo.save(successor)


async def lock(
    repo: IControlledDocumentRepository[D],
    document: D,
    actor: User,
    *,
    label: str,
    take_over: bool,
    may_take_over: bool,
) -> tuple[D, int | None]:
    """Gives `actor` the edit lock of `document`, or renews the one they
    hold. Another editor's live lock is taken over only when asked to and
    allowed; the second value names that editor so they can be told."""
    now = now_utc()
    if not take_over:
        document_control.assert_not_locked_by_other(document, actor, now, label)
    holder = document.lock_holder_id(now)
    if holder not in (None, actor.id) and not may_take_over:
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot take over editing of {label}."
        )
    previous = document_control.take_lock(document, actor, now)
    return await repo.save(document), previous


async def people_of(repo: IControlledDocumentRepository[D], document: D) -> list[int]:
    """Everyone who created or saved any revision of the document."""
    people: set[int] = set()
    for revision in await repo.get_lineage(document.lineage):
        people.add(revision.creator_id)
        people.update(revision.editor_ids)
    return sorted(people)


async def end_lock(
    repo: IControlledDocumentRepository[D],
    document: D,
    actor: User,
    *,
    force: bool,
    may_force: bool,
) -> tuple[D, int | None]:
    """Ends the edit lock of `document`: the actor's own, or with `force`
    anyone's, which needs `may_force`. Without `force` a lock of someone
    else is left alone, so a page that lost its lock can close quietly. The
    second value names the editor whose live lock was ended."""
    now = now_utc()
    holder = document.lock_holder_id(now)
    if holder is None:
        return document, None
    if holder == actor.id:
        document_control.release_lock(document, actor, now)
        return await repo.save(document), None
    if not force:
        return document, None
    if not may_force:
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot end another user's editing."
        )
    name = document.locked_by_full_name or f"user #{holder}"
    document_control.drop_lock(document)
    document.changes = append_changelog(
        document.changes, actor.full_name, f"Ended the editing of {name}."
    )
    return await repo.save(document), holder


async def release(repo: IControlledDocumentRepository[D], document: D, actor: User) -> D:
    previous = await predecessor_of(repo, document)
    document_control.release(document, previous, actor, now_utc())
    if previous is not None:
        await repo.save(previous)
    return await repo.save(document)


async def mark_invalid(
    repo: IControlledDocumentRepository[D], document: D, actor: User, reason: str
) -> D:
    document_control.mark_invalid(document, actor, now_utc(), reason.strip())
    return await repo.save(document)


async def delete_latest(repo: IControlledDocumentRepository[D], document: D, actor: User) -> None:
    """Deletes the latest revision; the one before it becomes the latest again."""
    previous = await predecessor_of(repo, document)
    # The deleted row gives up being the latest before the previous revision
    # claims it again.
    await repo.delete(document)
    if previous is not None:
        document_control.restore_latest(previous, document.revision, actor, now_utc())
        await repo.save(previous)


async def assert_owner_exists(
    project_repo: IProjectQueries,
    product_repo: IProductQueries,
    project_id: int | None,
    product_id: int | None,
    *,
    valid_owner: Callable[[int | None, int | None], None],
    plural: str,
) -> None:
    """Checks the project or product a document is being attached to:
    `valid_owner` applies the kind's own owner rule first, then the owner
    must exist and a product must not be archived. `plural` names the kind
    in the message, such as "calculations". Only called when the owner is
    new or changes, so a draft on a product that was archived later can
    still be edited where it is."""
    valid_owner(project_id, product_id)
    if project_id is not None and await project_repo.get_by_id(project_id) is None:
        raise ProjectNotFoundError(f"Project #{project_id} not found.")
    if product_id is not None:
        product = found_or_raise(
            await product_repo.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        if product.archived:
            raise ProductArchivedError(
                f"Product #{product_id} is archived; {plural} cannot be attached to it."
            )
