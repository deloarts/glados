"""
Round-trip coverage for AdminPdmSettingsOrmModel's connection/session
columns and SqlAlchemyAdminSettingsRepository.save_pdm_session, added
alongside the SolidWorks PDM Web API connection fields. No existing test
exercised the admin settings repository directly against the database for
any domain, so this is a new, narrowly scoped file rather than an
extension of one.
"""

import dataclasses
from datetime import UTC
from datetime import datetime

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder


def _as_utc(value: datetime) -> datetime:
    """SQLite (this suite's engine) has no native timezone-aware storage:
    a tz-aware value written through DateTime(timezone=True) reads back
    naive, wall-clock digits preserved. Normalises the read-back value so
    a test can still assert against the tz-aware value it wrote."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def test_save_pdm_round_trips_the_connection_fields(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()

    saved = await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=current.made_item_variable_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=True,
            base_url="http://pdm.example.local:65453",
            vault_name="MainVault",
            username="svc-glados",
            password="s3cret",
            verify_certificate=False,
            timeout_seconds=30,
            session_token="jwt-abc",
            session_user_id=7,
            session_obtained_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            watched_folders=[
                PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True),
                PdmWatchedFolder(
                    path="\\Bought-Parts", kind="bought", recursive=True, enabled=False
                ),
                PdmWatchedFolder(
                    path="\\Exported Documents",
                    kind="documents",
                    recursive=True,
                    enabled=True,
                    match_by="filename",
                    filename_pattern=r"^(?P<part_number>[A-Z0-9-]+)_(?P<revision>[A-Z0-9]+)\.pdf$",
                ),
            ],
            made_released_state_ids=[5],
            made_obsolete_state_ids=[9],
            made_replaced_state_ids=[9],
            bought_released_state_ids=[5],
            bought_obsolete_state_ids=[9],
            bought_replaced_state_ids=[9],
            poll_interval_minutes=30,
            vault_id="a1b2c3d4-0000-0000-0000-000000000000",
            cad_items_read_only=False,
            last_poll_at=datetime(2026, 9, 3, 11, 0, tzinfo=UTC),
            last_poll_error="timeout",
            last_poll_summary="3 seen, 1 ingested",
            writeback_enabled=True,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=True,
            stuck_after_days=7,
            reconcile_requested_deep=None,
            required_fields={"made": ["material", "fabrication_step"], "bought": []},
            set_approver_from_pdm=True,
        )
    )
    await db.commit()

    assert saved.enabled is True
    assert saved.base_url == "http://pdm.example.local:65453"
    assert saved.vault_name == "MainVault"
    assert saved.username == "svc-glados"
    assert saved.password == "s3cret"
    assert saved.verify_certificate is False
    assert saved.timeout_seconds == 30
    assert saved.session_token == "jwt-abc"
    assert saved.session_user_id == 7
    assert _as_utc(saved.session_obtained_at) == datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    assert saved.watched_folders == [
        PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True),
        PdmWatchedFolder(path="\\Bought-Parts", kind="bought", recursive=True, enabled=False),
        PdmWatchedFolder(
            path="\\Exported Documents",
            kind="documents",
            recursive=True,
            enabled=True,
            match_by="filename",
            filename_pattern=r"^(?P<part_number>[A-Z0-9-]+)_(?P<revision>[A-Z0-9]+)\.pdf$",
        ),
    ]
    assert saved.made_released_state_ids == [5]
    assert saved.made_obsolete_state_ids == [9]
    assert saved.bought_released_state_ids == [5]
    assert saved.bought_obsolete_state_ids == [9]
    assert saved.poll_interval_minutes == 30
    assert saved.vault_id == "a1b2c3d4-0000-0000-0000-000000000000"
    assert saved.cad_items_read_only is False
    assert _as_utc(saved.last_poll_at) == datetime(2026, 9, 3, 11, 0, tzinfo=UTC)
    assert saved.last_poll_error == "timeout"
    assert saved.last_poll_summary == "3 seen, 1 ingested"
    assert saved.writeback_enabled is True
    assert saved.made_item_extensions == ["sldprt"]
    assert saved.bought_item_extensions == ["sldprt", "sldasm"]
    assert saved.document_categories == {
        "pdf": "drawing",
        "dxf": "dxf",
        "step": "step",
        "stp": "step",
    }
    assert saved.thumbnails_enabled is True
    assert saved.required_fields == {"made": ["material", "fabrication_step"], "bought": []}
    assert saved.set_approver_from_pdm is True

    # A fresh read (new repository instance, same session) proves it was
    # actually persisted, not just echoed back from the entity passed in.
    reread = await SqlAlchemyAdminSettingsRepository(db).get_pdm()
    assert reread.base_url == "http://pdm.example.local:65453"
    assert reread.session_token == "jwt-abc"
    assert reread.watched_folders == saved.watched_folders
    assert reread.required_fields == {"made": ["material", "fabrication_step"], "bought": []}
    assert reread.vault_id == "a1b2c3d4-0000-0000-0000-000000000000"
    assert reread.writeback_enabled is True
    assert reread.made_item_extensions == ["sldprt"]
    assert reread.bought_item_extensions == ["sldprt", "sldasm"]
    assert reread.document_categories == saved.document_categories
    assert reread.thumbnails_enabled is True
    assert reread.set_approver_from_pdm is True


async def test_seeded_row_defaults_to_an_unconfigured_connection(db) -> None:
    """conftest's autouse _seed_admin_settings inserts
    AdminPdmSettingsOrmModel(id=1, enabled=False) explicitly (UpdatePdmSettings
    branches on `enabled`) and relies on the
    ORM column defaults for everything else, the same defaults init_db.py
    seeds explicitly in a real deployment.

    `verify_certificate` and `writeback_enabled` are deliberately not
    asserted here: SQLite stores a Boolean server_default such as "true"
    or "false" as the literal text, and SQLAlchemy's generic
    (non-native-boolean) result processor does `bool(value)` on it, so a
    value that was never explicitly written by an INSERT/UPDATE reads
    back truthy regardless of which literal it is, "false" included.
    This is a pre-existing property of every Boolean server_default in
    this module (e.g. AdminAuthSettingsOrmModel.ldap_enabled), not
    something new here; Postgres (the real database) does not have this
    problem, and no production code path ever depends on either column
    reading correctly without an explicit save: init_db.py always passes
    both explicitly, see save_pdm's own test above for the explicit-value
    path."""
    settings = await SqlAlchemyAdminSettingsRepository(db).get_pdm()

    assert settings.enabled is False
    assert settings.base_url == ""
    assert settings.vault_name == ""
    assert settings.username == ""
    assert settings.password is None
    assert settings.timeout_seconds == 15
    assert settings.session_token is None
    assert settings.session_user_id is None
    assert settings.session_obtained_at is None
    assert settings.is_configured is False
    assert settings.watched_folders == []
    assert settings.made_released_state_ids == []
    assert settings.made_obsolete_state_ids == []
    assert settings.bought_released_state_ids == []
    assert settings.bought_obsolete_state_ids == []
    assert settings.poll_interval_minutes == 15
    assert settings.vault_id == ""
    assert settings.last_poll_at is None
    assert settings.last_poll_error is None
    assert settings.last_poll_summary is None


async def test_save_pdm_session_updates_only_the_session_columns(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map={},
            bought_item_variable_map={},
            enabled=True,
            base_url="http://pdm.example.local:65453",
            vault_name="MainVault",
            username="svc-glados",
            password="s3cret",
            verify_certificate=True,
            timeout_seconds=15,
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
            watched_folders=[],
            made_released_state_ids=[],
            made_obsolete_state_ids=[],
            made_replaced_state_ids=[],
            bought_released_state_ids=[],
            bought_obsolete_state_ids=[],
            bought_replaced_state_ids=[],
            poll_interval_minutes=15,
            vault_id="",
            cad_items_read_only=True,
            last_poll_at=None,
            last_poll_error=None,
            last_poll_summary=None,
            writeback_enabled=False,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=False,
            stuck_after_days=7,
            reconcile_requested_deep=None,
            required_fields={"made": [], "bought": []},
        )
    )
    await db.commit()

    obtained_at = datetime(2026, 9, 3, 8, 30, tzinfo=UTC)
    await repo.save_pdm_session(token="jwt-xyz", user_id=42, obtained_at=obtained_at)
    await db.commit()

    settings = await repo.get_pdm()
    assert settings.session_token == "jwt-xyz"
    assert settings.session_user_id == 42
    assert _as_utc(settings.session_obtained_at) == obtained_at
    # Untouched by save_pdm_session.
    assert settings.base_url == "http://pdm.example.local:65453"
    assert settings.vault_name == "MainVault"
    assert settings.username == "svc-glados"
    assert settings.password == "s3cret"
    assert settings.enabled is True


async def test_save_pdm_session_can_clear_the_stored_session(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm_session(
        token="jwt-to-clear", user_id=1, obtained_at=datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
    )
    await db.commit()

    await repo.save_pdm_session(token=None, user_id=None, obtained_at=None)
    await db.commit()

    settings = await repo.get_pdm()
    assert settings.session_token is None
    assert settings.session_user_id is None
    assert settings.session_obtained_at is None


async def test_save_pdm_poll_status_updates_only_the_poll_status_columns(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map={},
            bought_item_variable_map={},
            enabled=True,
            base_url="http://pdm.example.local:65453",
            vault_name="MainVault",
            username="svc-glados",
            password="s3cret",
            verify_certificate=True,
            timeout_seconds=15,
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
            watched_folders=[],
            made_released_state_ids=[],
            made_obsolete_state_ids=[],
            made_replaced_state_ids=[],
            bought_released_state_ids=[],
            bought_obsolete_state_ids=[],
            bought_replaced_state_ids=[],
            poll_interval_minutes=15,
            vault_id="",
            cad_items_read_only=True,
            last_poll_at=None,
            last_poll_error=None,
            last_poll_summary=None,
            writeback_enabled=False,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=False,
            stuck_after_days=7,
            reconcile_requested_deep=None,
            required_fields={"made": [], "bought": []},
        )
    )
    await db.commit()

    at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)
    await repo.save_pdm_poll_status(at=at, error="host unreachable", summary=None)
    await db.commit()

    settings = await repo.get_pdm()
    assert _as_utc(settings.last_poll_at) == at
    assert settings.last_poll_error == "host unreachable"
    assert settings.last_poll_summary is None
    # Untouched by save_pdm_poll_status.
    assert settings.base_url == "http://pdm.example.local:65453"
    assert settings.enabled is True


async def test_save_pdm_poll_status_can_clear_last_poll_at(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm_poll_status(
        at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC), error=None, summary="5 seen, 2 ingested"
    )
    await db.commit()

    await repo.save_pdm_poll_status(at=None, error=None, summary=None)
    await db.commit()

    settings = await repo.get_pdm()
    assert settings.last_poll_at is None
    assert settings.last_poll_error is None
    assert settings.last_poll_summary is None


async def test_save_pdm_vault_id_updates_only_the_vault_id_column(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm_vault_id("a1b2c3d4-0000-0000-0000-000000000000")
    await db.commit()

    settings = await repo.get_pdm()
    assert settings.vault_id == "a1b2c3d4-0000-0000-0000-000000000000"


async def test_save_pdm_round_trips_the_document_released_states(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    assert current.document_released_state_ids == []

    await repo.save_pdm(dataclasses.replace(current, document_released_state_ids=[12, 14]))
    await db.commit()

    reread = await SqlAlchemyAdminSettingsRepository(db).get_pdm()
    assert reread.document_released_state_ids == [12, 14]


async def test_save_pdm_round_trips_the_document_excluded_kinds(db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    assert current.document_excluded_kinds == {}

    await repo.save_pdm(
        dataclasses.replace(
            current, document_excluded_kinds={"step": ["bought"], "stp": ["bought"]}
        )
    )
    await db.commit()

    reread = await SqlAlchemyAdminSettingsRepository(db).get_pdm()
    assert reread.document_excluded_kinds == {"step": ["bought"], "stp": ["bought"]}
