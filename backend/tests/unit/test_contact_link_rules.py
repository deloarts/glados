"""
How a project's contacts follow from its product's links and its own:
inherited contacts first with the project's override, then its own, and
the permissions of the links.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.services.contact_link_rules import ResolvedProjectContact
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from tests.factories import make_user

_NOW = datetime(2026, 11, 10, tzinfo=UTC)


def _link(owner: ContactLinkOwner, contact_id: int, receives: bool) -> ContactLink:
    return ContactLink(
        id=contact_id,
        owner=owner,
        owner_id=1,
        contact_id=contact_id,
        receives_meeting_notes=receives,
        created=_NOW,
        creator_id=1,
    )


def _product(contact_id: int, receives: bool = True) -> ContactLink:
    return _link(ContactLinkOwner.PRODUCT, contact_id, receives)


def _project(contact_id: int, receives: bool = True) -> ContactLink:
    return _link(ContactLinkOwner.PROJECT, contact_id, receives)


def test_inherited_contacts_come_first_with_the_products_flag() -> None:
    resolved = ContactLinkRules.resolve_project_contacts(
        [_product(1, True), _product(2, False)], [_project(3, True)]
    )

    assert resolved == [
        ResolvedProjectContact(1, True, True, True, False),
        ResolvedProjectContact(2, True, False, False, False),
        ResolvedProjectContact(3, False, True, None, False),
    ]


def test_a_project_row_for_an_inherited_contact_overrides_the_flag() -> None:
    resolved = ContactLinkRules.resolve_project_contacts([_product(1, True)], [_project(1, False)])

    assert resolved == [ResolvedProjectContact(1, True, False, True, True)]


def test_a_project_can_switch_on_what_its_product_switched_off() -> None:
    resolved = ContactLinkRules.resolve_project_contacts([_product(1, False)], [_project(1, True)])

    assert resolved[0].receives_meeting_notes is True
    assert resolved[0].overridden is True


def test_no_product_leaves_the_projects_own_links() -> None:
    resolved = ContactLinkRules.resolve_project_contacts([], [_project(4, False)])

    assert resolved == [ResolvedProjectContact(4, False, False, None, False)]


def test_reading_links_needs_read_contacts() -> None:
    nobody = make_user(permissions=[])
    reader = make_user(permissions=[Permission.READ_CONTACTS])

    with pytest.raises(InsufficientPermissionsError):
        ContactLinkRules.assert_can_read(nobody)
    ContactLinkRules.assert_can_read(reader)
