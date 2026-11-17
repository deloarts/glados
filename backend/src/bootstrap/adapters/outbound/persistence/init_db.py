"""Database initialisation at startup: migrations to head, the system user
synced from config, seeded admin settings, one unconfigured slot per print
classifier, re-encryption of stored secrets and the time tracking fingerprint
recomputation that must follow it. Every step is idempotent."""

from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import ADMIN_SETTINGS_SEEDS
from src.modules.operations.adapters.outbound.persistence.time_tracking_fingerprints import (
    recompute_time_tracking_fingerprints,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.encrypted_type import (
    reencrypt_stored_secrets,
)
from src.modules.platform.const import SERVER_DEFAULT_DATE_FORMAT
from src.modules.platform.const import SERVER_DEFAULT_LANGUAGE
from src.modules.platform.const import SERVER_DEFAULT_START_PAGE
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.infrastructure.security.hashing import averify_hash
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository
from src.shared_kernel.domain.services.clock import now_utc


def run_migrations() -> None:
    """Applies pending migrations; runs first in the lifespan."""
    from alembic import command
    from alembic.config import Config

    log.info("Running Alembic migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    log.info("Migrations complete.")


_SEED_ATTEMPTS = 3


class InitDatabase:
    """Seeds the database with required initial data."""

    def __init__(
        self,
        user_repo: IUserRepository,
        admin_settings_repo: IAdminSettingsRepository,
        print_template_repo: IPrintTemplateRepository,
        db: AsyncSession,
    ) -> None:
        self._repo = user_repo
        self._admin_settings = admin_settings_repo
        self._print_templates = print_template_repo
        self._db = db

    async def run(self) -> None:
        db = self._db
        # Serializes seeding across workers on Postgres. The lock ends at the
        # first commit, so two workers can still race on a row; seeding is
        # idempotent, so the loser rolls back and runs the pass again. Every
        # worker queues for the lock while the ones ahead of it seed, which
        # can outlast the pool's lock_timeout, so the wait lifts it for this
        # transaction as advisory_lock_blocking does; a worker that gave up
        # would fail to boot and take the whole server down with it.
        for attempt in range(1, _SEED_ATTEMPTS + 1):
            try:
                if db.get_bind().dialect.name == "postgresql":
                    await db.execute(text("SET LOCAL lock_timeout = 0"))
                    await db.execute(
                        text("SELECT pg_advisory_xact_lock(:key)"),
                        {"key": int(AdvisoryLockKey.INIT_DB_SEED)},
                    )
                await self._ensure_system_user()
                await self._ensure_admin_settings()
                await self._ensure_print_template_slots()
                await reencrypt_stored_secrets(db)
                await recompute_time_tracking_fingerprints(db)
                return
            except IntegrityError:
                await db.rollback()
                if attempt == _SEED_ATTEMPTS:
                    raise
                log.info("Another worker seeded concurrently; repeating the seed pass.")

    # ── System user ───────────────────────────────────────────────────

    async def _ensure_system_user(self) -> None:
        existing = await self._repo.get_by_username(SYSTEM_USER)
        if not existing:
            log.info("System user not found, creating.")
            await self._create_system_user()
        else:
            log.info("System user found, syncing credentials from config.")
            await self._sync_system_user(existing)

    async def _create_system_user(self) -> None:
        from datetime import UTC
        from datetime import datetime

        system_user = User(
            id=0,
            username=SYSTEM_USER,
            full_name=cfg.init.full_name,
            email=cfg.init.mail,
            created=datetime.now(UTC),
            hashed_password=await aget_hash(cfg.init.password),
            is_active=True,
            is_systemuser=True,
            permissions=[],
            language=Language(SERVER_DEFAULT_LANGUAGE),
            date_format=DateFormat(SERVER_DEFAULT_DATE_FORMAT),
            start_page=StartPage(SERVER_DEFAULT_START_PAGE),
            theme_preset=ThemePreset.Aura,
            theme_surface=ThemeSurface.glados,
            theme_primary=ThemePrimary.glados,
            theme_dark_mode=True,
            button_flat_style=False,
            table_gridlines=False,
            table_striped_rows=False,
        )
        saved = await self._repo.save(system_user)
        await self._db.commit()
        log.info(f"System user created (ID={saved.id}).")

    async def _sync_system_user(self, existing: User) -> None:
        drifted = (
            existing.full_name != cfg.init.full_name
            or existing.email != cfg.init.mail
            or existing.is_active is not True
            or existing.is_systemuser is not True
            or not await averify_hash(cfg.init.password, existing.hashed_password)
        )
        if drifted:
            log.warning("System user credentials drifted from config, resyncing.")

        existing.full_name = cfg.init.full_name
        existing.email = cfg.init.mail
        existing.hashed_password = await aget_hash(cfg.init.password)
        existing.is_active = True
        existing.is_systemuser = True

        await self._repo.save(existing)
        await self._db.commit()
        log.info(f"System user synced (ID={existing.id}).")

    # ── Admin settings ────────────────────────────────────────────────

    async def _ensure_admin_settings(self) -> None:
        """Seeds every absent settings row; existing rows are never touched,
        so admin changes survive restarts."""
        for seed in ADMIN_SETTINGS_SEEDS:
            exists = await self._db.scalar(select(seed.model).filter_by(id=1).limit(1))
            if exists is not None:
                continue
            await seed.save(self._admin_settings)(seed.build())
            await self._db.commit()
            log.info(f"Admin {seed.label} settings seeded.")

    # ── Print template slots ──────────────────────────────────────────

    async def _ensure_print_template_slots(self) -> None:
        """Creates the row of every print classifier that has none, as an
        unconfigured slot: switched off, without content, with the
        classifier's default trigger. Existing rows are never touched. A
        fresh install ships no print designs; an admin imports them."""
        existing = {template.classifier for template in await self._print_templates.get_all()}
        for classifier, spec in CLASSIFIERS.items():
            if classifier in existing:
                continue
            await self._print_templates.save(
                PrintTemplate(
                    id=0,
                    created=now_utc(),
                    changed=None,
                    changes=[],
                    classifier=classifier,
                    trigger=spec.default_trigger,
                    source=None,
                    paper="a4" if spec.output_kind == PrintOutputKind.PDF_DOCKET else None,
                    enabled=False,
                )
            )
            await self._db.commit()
            log.info(f"Print template slot {classifier.value!r} created.")
