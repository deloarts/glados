"""
The contacts of a project: its product's links, which it inherits, and its
own. A project sets the meeting notes flag of an inherited contact for
itself through a project link of its own, which is how it mutes one; it
cannot unlink an inherited contact, since that link is the product's.
Reading needs read:contacts and every change write:contacts; each change
answers the project's list as it is afterwards.
"""

from src.modules.catalogue.ports.outbound.catalogue_queries import IContactQueries
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.contact_link_dto import LinkContactCommand
from src.modules.workspace.application.dto.contact_link_dto import ProjectContactResult
from src.modules.workspace.application.use_cases.contact_link._support import linkable_contact
from src.modules.workspace.application.use_cases.contact_link._support import load_project
from src.modules.workspace.application.use_cases.contact_link._support import product_links_of
from src.modules.workspace.application.use_cases.contact_link._support import project_contacts
from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ContactAlreadyLinkedError
from src.modules.workspace.domain.errors import ContactLinkNotFoundError
from src.modules.workspace.domain.errors import InheritedContactLinkError
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.services.project_rules import ProjectRules
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.shared_kernel.domain.services.clock import now_utc


class _ProjectContactUseCase:
    def __init__(
        self,
        link_repo: IContactLinkRepository,
        project_repo: IProjectRepository,
        contact_queries: IContactQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._links = link_repo
        self._projects = project_repo
        self._contacts = contact_queries
        self._uow = uow

    async def _inherited(self, project: Project, contact_id: int) -> ContactLink | None:
        for link in await product_links_of(self._links, project):
            if link.contact_id == contact_id:
                return link
        return None

    def _new_link(
        self, actor: User, project: Project, contact_id: int, receives_meeting_notes: bool
    ) -> ContactLink:
        return ContactLink(
            id=0,
            owner=ContactLinkOwner.PROJECT,
            owner_id=project.id,
            contact_id=contact_id,
            receives_meeting_notes=receives_meeting_notes,
            created=now_utc(),
            creator_id=actor.id,
        )


class GetProjectContacts(_ProjectContactUseCase):
    async def execute(self, actor: User, project_id: int) -> list[ProjectContactResult]:
        ContactLinkRules.assert_can_read(actor)
        project = await load_project(self._projects, project_id)
        return await project_contacts(self._links, self._contacts, project)


class LinkProjectContact(_ProjectContactUseCase):
    async def execute(
        self, actor: User, project_id: int, cmd: LinkContactCommand
    ) -> list[ProjectContactResult]:
        project = await load_project(self._projects, project_id)
        ProjectRules.assert_can_update(actor, project)
        await linkable_contact(self._contacts, cmd.contact_id)
        if await self._inherited(project, cmd.contact_id) is not None:
            raise ContactAlreadyLinkedError(
                f"Contact #{cmd.contact_id} is linked to the product of project "
                f"#{project_id}, so the project has it already."
            )
        if await self._links.get_link(ContactLinkOwner.PROJECT, project_id, cmd.contact_id):
            raise ContactAlreadyLinkedError(
                f"Contact #{cmd.contact_id} is linked to project #{project_id} already."
            )
        await self._links.save(
            self._new_link(actor, project, cmd.contact_id, cmd.receives_meeting_notes)
        )
        await self._uow.commit()
        log.info(f"Linked contact ID={cmd.contact_id} to project ID={project_id}.")
        return await project_contacts(self._links, self._contacts, project)


class SetProjectContactMeetingNotes(_ProjectContactUseCase):
    async def execute(
        self, actor: User, project_id: int, contact_id: int, receives_meeting_notes: bool
    ) -> list[ProjectContactResult]:
        """For an inherited contact, a flag that matches the product's drops
        the project's override, so the project follows the product again;
        any other flag is kept as the override."""
        project = await load_project(self._projects, project_id)
        ProjectRules.assert_can_update(actor, project)
        inherited = await self._inherited(project, contact_id)
        own = await self._links.get_link(ContactLinkOwner.PROJECT, project_id, contact_id)
        if inherited is None and own is None:
            raise ContactLinkNotFoundError(
                f"Contact #{contact_id} is not linked to project #{project_id}."
            )
        if inherited is not None and inherited.receives_meeting_notes == receives_meeting_notes:
            if own is not None:
                await self._links.delete(own)
        elif own is None:
            await self._links.save(
                self._new_link(actor, project, contact_id, receives_meeting_notes)
            )
        elif own.receives_meeting_notes != receives_meeting_notes:
            own.receives_meeting_notes = receives_meeting_notes
            await self._links.save(own)
        await self._uow.commit()
        return await project_contacts(self._links, self._contacts, project)


class UnlinkProjectContact(_ProjectContactUseCase):
    async def execute(
        self, actor: User, project_id: int, contact_id: int
    ) -> list[ProjectContactResult]:
        project = await load_project(self._projects, project_id)
        ProjectRules.assert_can_update(actor, project)
        if await self._inherited(project, contact_id) is not None:
            raise InheritedContactLinkError(
                f"Contact #{contact_id} comes from the product of project #{project_id}; "
                "mute it for the project instead."
            )
        own = await self._links.get_link(ContactLinkOwner.PROJECT, project_id, contact_id)
        if own is None:
            raise ContactLinkNotFoundError(
                f"Contact #{contact_id} is not linked to project #{project_id}."
            )
        await self._links.delete(own)
        await self._uow.commit()
        log.info(f"Unlinked contact ID={contact_id} from project ID={project_id}.")
        return await project_contacts(self._links, self._contacts, project)
