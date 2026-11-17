"""
Tests for token_permission_rules.py: the shared PAT/API-key permission
grant rules, and SOLIDWORKS_ADDIN_SCOPES, the permission set the SolidWorks
add-in's own PAT needs. The rules a PAT endpoint enforces are checked deep
inside its use case rather than declared on the route, so they are not
mechanically introspectable here; this pins the set instead, with the
endpoint-by-endpoint derivation documented next to the constant itself in
token_permission_rules.py.
"""

from src.modules.platform.domain.services.token_permission_rules import NEVER_GRANTABLE_TO_TOKENS
from src.modules.platform.domain.services.token_permission_rules import SOLIDWORKS_ADDIN_SCOPES
from src.modules.platform.domain.value_objects.permission import Permission


class TestSolidworksAddinScopes:
    def test_pinned_to_source_items_and_the_data_portal(self):
        """The add-in's PAT calls two kinds of endpoint that require a
        permission: POST pat/source-items/, gated on write:source_items, and
        the Data Portal match, search and picture, gated on use:data_portal.
        Every other endpoint it calls needs nothing beyond a valid PAT. See
        the comment above SOLIDWORKS_ADDIN_SCOPES."""
        assert SOLIDWORKS_ADDIN_SCOPES == (
            Permission.WRITE_SOURCE_ITEMS,
            Permission.USE_DATA_PORTAL,
        )

    def test_every_scope_exists_in_the_permission_catalogue(self):
        assert set(SOLIDWORKS_ADDIN_SCOPES) <= set(Permission.ALL)

    def test_no_scope_is_on_the_never_grantable_list(self):
        """A scope a PAT could never actually be granted would make the
        add-in token shortcut unusable, so this set must stay disjoint from
        NEVER_GRANTABLE_TO_TOKENS (settings/API-key management)."""
        assert set(SOLIDWORKS_ADDIN_SCOPES).isdisjoint(NEVER_GRANTABLE_TO_TOKENS)
