"""
Pins InitDatabase._ensure_admin_settings' seed literals for the domains
whose defaults this test module covers, plus the cross-cutting rule every
"new-installs-only" claim here depends on: a domain is only ever seeded
once, an existing row is never re-seeded or patched (see init_db.py's
module docstring, point 1).

No database: `IAdminSettingsRepository._db` is faked just enough to answer
the `id=1` existence check `_ensure_admin_settings` makes before seeding
each domain, whether it runs as a legacy Query or as a `select()` statement,
and every `save_*` is captured rather than persisted.
"""

from typing import Any

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.auth import (
    AdminAuthSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.features import (
    AdminFeatureSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.security import (
    AdminSecuritySettingsOrmModel,
)


class _FakeQuery:
    def __init__(self, result: object | None) -> None:
        self._result = result

    def filter_by(self, **kwargs: Any) -> "_FakeQuery":
        return self

    def first(self) -> object | None:
        return self._result


class _FakeDb:
    """Answers the `id=1` existence check as "exists" for whichever ORM
    model classes are passed in, "absent" otherwise."""

    def __init__(self, existing: set[type] | None = None) -> None:
        self._existing = existing or set()

    def query(self, model_class: type) -> _FakeQuery:
        return _FakeQuery(object() if model_class in self._existing else None)

    async def scalar(self, stmt: Any) -> object | None:
        model_class = stmt.column_descriptions[0]["entity"]
        return object() if model_class in self._existing else None

    async def commit(self) -> None:
        pass


class FakeAdminSettingsRepo:
    """Captures whatever each save_* is called with, keyed by domain name,
    a real SqlAlchemyAdminSettingsRepository would upsert to the DB instead."""

    def __init__(self, existing: set[type] | None = None) -> None:
        self._db = _FakeDb(existing)
        self.saved: dict[str, Any] = {}

    def _capture(self, domain: str, s: Any) -> Any:
        self.saved[domain] = s
        return s

    async def save_host(self, s: Any) -> Any:
        return self._capture("host", s)

    async def save_mail(self, s: Any) -> Any:
        return self._capture("mail", s)

    async def save_auth(self, s: Any) -> Any:
        return self._capture("auth", s)

    async def save_storage(self, s: Any) -> Any:
        return self._capture("storage", s)

    async def save_security(self, s: Any) -> Any:
        return self._capture("security", s)

    async def save_features(self, s: Any) -> Any:
        return self._capture("features", s)

    async def save_general(self, s: Any) -> Any:
        return self._capture("general", s)

    async def save_branding(self, s: Any) -> Any:
        return self._capture("branding", s)

    async def save_notifications(self, s: Any) -> Any:
        return self._capture("notifications", s)

    async def save_maintenance(self, s: Any) -> Any:
        return self._capture("maintenance", s)

    async def save_retention(self, s: Any) -> Any:
        return self._capture("retention", s)

    async def save_orders(self, s: Any) -> Any:
        return self._capture("orders", s)

    async def save_made_items(self, s: Any) -> Any:
        return self._capture("made_items", s)

    async def save_pdm(self, s: Any) -> Any:
        return self._capture("pdm", s)

    async def save_stock(self, s: Any) -> Any:
        return self._capture("stock", s)

    async def save_production(self, s: Any) -> Any:
        return self._capture("production", s)

    async def save_planning(self, s: Any) -> Any:
        return self._capture("planning", s)

    async def save_banner(self, s: Any) -> Any:
        return self._capture("banner", s)

    async def save_agents(self, s: Any) -> Any:
        return self._capture("agents", s)

    async def save_data_import(self, s: Any) -> Any:
        return self._capture("data_import", s)

    async def save_edp(self, s: Any) -> Any:
        return self._capture("edp", s)


async def _seed(existing: set[type] | None = None) -> FakeAdminSettingsRepo:
    repo = FakeAdminSettingsRepo(existing)
    init_db = InitDatabase(
        user_repo=None,  # type: ignore[arg-type]
        admin_settings_repo=repo,  # type: ignore[arg-type]
        print_template_repo=None,  # type: ignore[arg-type]
        db=repo._db,  # type: ignore[arg-type]
    )
    await init_db._ensure_admin_settings()
    return repo


async def test_auth_seed_verifies_certificates():
    """The seeded AdminAuthSettings verifies LDAP server
    certificates by default on a fresh install."""
    repo = await _seed()
    assert repo.saved["auth"].ldap_verify_certificate is True


async def test_features_seed_allows_private_webhook_targets():
    """A fresh install lets webhooks reach private ranges such as RFC 1918.
    Loopback, link-local and the stack's own network are refused by the
    target guard regardless of this flag."""
    repo = await _seed()
    assert repo.saved["features"].allow_private_webhooks is True


async def test_security_seed_sets_a_login_limit():
    """A fresh install ships online-brute-force protection for
    password login, 5 attempts / 15 minutes."""
    repo = await _seed()
    assert repo.saved["security"].max_login_attempts == 5
    assert repo.saved["security"].lockout_duration_minutes == 15


async def test_seeding_skips_domains_that_already_exist():
    """Cross-cutting rule: every "new-installs-only" claim in this test
    module depends on it: a domain whose row already exists is left
    alone, never re-seeded or patched, while every other still-absent
    domain still gets seeded in the same pass."""
    repo = await _seed(
        existing={
            AdminAuthSettingsOrmModel,
            AdminFeatureSettingsOrmModel,
            AdminSecuritySettingsOrmModel,
        }
    )
    assert "auth" not in repo.saved
    assert "features" not in repo.saved
    assert "security" not in repo.saved
    # Domains that were absent are still seeded in the same pass.
    assert "mail" in repo.saved
    assert "storage" in repo.saved
    assert "host" in repo.saved


async def test_domains_are_seeded_and_logged_in_a_fixed_order(glados_caplog):
    """Pins the seeding order and the one info line per seeded domain."""
    repo = await _seed(existing={AdminFeatureSettingsOrmModel})
    order = [
        ("host", "host"),
        ("mail", "mail"),
        ("auth", "auth"),
        ("storage", "storage"),
        ("security", "security"),
        ("general", "general"),
        ("branding", "branding"),
        ("notifications", "notification"),
        ("maintenance", "maintenance"),
        ("retention", "retention"),
        ("orders", "order"),
        ("made_items", "made item"),
        ("pdm", "PDM"),
        ("production", "production"),
        ("planning", "planning"),
        ("banner", "banner"),
        ("agents", "agent"),
        ("data_import", "data import"),
        ("edp", "EPLAN Data Portal"),
        ("stock", "stock service"),
    ]
    assert list(repo.saved) == [domain for domain, _ in order]
    assert [r.getMessage() for r in glados_caplog.records] == [
        f"Admin {label} settings seeded." for _, label in order
    ]
