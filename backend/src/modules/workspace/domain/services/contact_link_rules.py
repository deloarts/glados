"""
Pure rules for the contact links of products and projects: who may read
them, and how a project's list follows from its own links and
its product's. No I/O.
"""

from dataclasses import dataclass

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.contact_link import ContactLink


@dataclass(frozen=True)
class ResolvedProjectContact:
    """One contact of a project as the project sees it. An inherited
    contact comes from the product; a project link for it overrides the
    product's flag, which is how a project mutes it."""

    contact_id: int
    inherited: bool
    receives_meeting_notes: bool
    # The product's flag of an inherited contact, None for the project's own.
    product_receives_meeting_notes: bool | None
    # An inherited contact whose flag the project set for itself.
    overridden: bool


class ContactLinkRules:
    @staticmethod
    def assert_can_read(actor: User) -> None:
        assert_has_permission(actor, Permission.READ_CONTACTS, "read", "contact links")

    @staticmethod
    def resolve_project_contacts(
        product_links: list[ContactLink], project_links: list[ContactLink]
    ) -> list[ResolvedProjectContact]:
        """The product's links first, each with the project's override if it
        has one, then the project's own links, each group in the order given."""
        own = {link.contact_id: link for link in project_links}
        resolved: list[ResolvedProjectContact] = []
        inherited_ids: set[int] = set()
        for link in product_links:
            inherited_ids.add(link.contact_id)
            override = own.get(link.contact_id)
            resolved.append(
                ResolvedProjectContact(
                    contact_id=link.contact_id,
                    inherited=True,
                    receives_meeting_notes=(
                        override.receives_meeting_notes
                        if override is not None
                        else link.receives_meeting_notes
                    ),
                    product_receives_meeting_notes=link.receives_meeting_notes,
                    overridden=override is not None,
                )
            )
        for link in project_links:
            if link.contact_id in inherited_ids:
                continue
            resolved.append(
                ResolvedProjectContact(
                    contact_id=link.contact_id,
                    inherited=False,
                    receives_meeting_notes=link.receives_meeting_notes,
                    product_receives_meeting_notes=None,
                    overridden=False,
                )
            )
        return resolved
