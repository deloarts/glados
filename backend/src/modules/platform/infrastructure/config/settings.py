"""
Pydantic settings classes that load configuration from environment
variables, grouped by concern (database, security, mail, storage, and so
on) and composed into the top-level `Settings` object read via `cfg`.
"""

import os
from ipaddress import IPv4Network
from ipaddress import IPv6Network
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import NoDecode
from pydantic_settings import SettingsConfigDict


class SecuritySettings(BaseModel):
    secret_key_persistent: str
    secret_key_non_persistent: str
    # Encrypts integration secrets stored in the database (see
    # src/modules/platform/infrastructure/security/secret_box.py). Deliberately separate from
    # the signing keys: rotating a signing key logs users out, rotating this
    # one without the previous value makes the stored secrets unreadable.
    # Optional so CLI scripts and dev setups still load, the boot guard
    # requires it in production.
    encryption_key: str | None = None
    # The key being rotated out. Still accepted for decryption, so stored
    # secrets stay readable until the next boot re-encrypts them.
    encryption_key_previous: str | None = None
    # Encrypts the database backup archives (see
    # src/modules/platform/infrastructure/security/backup_cipher.py). Separate
    # from encryption_key, so an archive never travels with the key to the
    # secrets inside it and losing one key never loses the other's data.
    # Optional so dev setups and CLI scripts still load; without it a
    # production process refuses to write a backup.
    backup_encryption_key: str | None = None

    algorithm: str = "HS256"
    min_pw_len: int = 8
    # Seed value only; the live value is the admin setting. Never read this
    # at request time, or the admin toggle would be ignored.
    allow_rfid_login: bool = True


class DatabaseSettings(BaseModel):
    # A SQLAlchemy URL. Postgres URLs name the psycopg (v3) driver,
    # postgresql+psycopg://, the only Postgres driver installed.
    url: str
    # Per-process pool. Gunicorn runs several workers, each with its own
    # pool, so workers x (pool_size + max_overflow) must stay well below the
    # server's max_connections, leaving room for backups, migrations and
    # admin consoles.
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout_seconds: int = 10
    # Server-side limits applied to every app connection. 0 disables one.
    # Connections that hold an advisory lock on purpose lift the idle and
    # lock limits for themselves (see advisory_lock.py).
    statement_timeout_seconds: int = 30
    lock_timeout_seconds: int = 5
    idle_in_transaction_timeout_seconds: int = 60
    # Statements slower than this are logged with their request context and
    # counted in glados_db_slow_queries_total. 0 disables the log.
    slow_query_threshold_ms: int = 500

    @property
    def async_url(self) -> str:
        """`url` in the form the async engine needs. psycopg 3 serves sync and
        async under one dialect name, so only SQLite (the test suite) swaps
        its driver for aiosqlite."""
        if self.url.startswith("sqlite://"):
            return "sqlite+aiosqlite://" + self.url.removeprefix("sqlite://")
        return self.url


class RedisSettings(BaseModel):
    url: str
    # Bounds every command on the shared clients, so a hung Redis fails a
    # call (and the fail-open paths answer) instead of blocking it forever.
    # socket_timeout must stay above the event workers' 1s XREADGROUP block.
    socket_timeout_seconds: float = 3.0
    socket_connect_timeout_seconds: float = 2.0
    max_connections: int = 50
    # Retries on connection errors and timeouts only, with a short backoff,
    # so a Redis restart is absorbed without multiplying a real outage's
    # latency on the login path.
    retries: int = 1


class InitSettings(BaseModel):
    full_name: str
    mail: str
    password: str


class LocalStorageSettings(BaseModel):
    base_dir: str = "./media"


class BackupSettings(BaseModel):
    # Where `admin pre-migration-dump` writes the dump the container
    # entrypoint takes before it applies pending migrations, and how many of
    # those dumps it keeps. A relative path resolves against the working
    # directory, /app in the image, where docker-compose.yml mounts a volume.
    pre_migration_dump_dir: str = "./pre-migration-dumps"
    pre_migration_dump_keep: int = 3


class NetworkSettings(BaseModel):
    # The subnets of the stack's own networks (env NETWORK__INTERNAL_SUBNETS,
    # comma separated), which docker-compose.yml pins and passes in. Only
    # the stack's services live there, so an outbound call whose target a
    # user chooses must never reach them. Empty outside the release compose
    # file. Which peers the server trusts for forwarded headers is gunicorn's
    # setting, NETWORK__TRUSTED_PROXIES in gunicorn_conf.py.
    internal_subnets: Annotated[tuple[IPv4Network | IPv6Network, ...], NoDecode] = ()

    @field_validator("internal_subnets", mode="before")
    @classmethod
    def _split_comma_list(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value


class PdmSettings(BaseModel):
    # The deployment's own switch for the admin API console's mutating PDM
    # Web API operations (check-in, delete, state changes and the like).
    # Off, the console refuses every one of them whatever the admin selects,
    # since Glados cannot undo them on a live vault.
    allow_mutating_operations: bool = False


class SchedulingSettings(BaseModel):
    # Writes only request a schedule walk, which the `schedule` event worker
    # runs; false walks in the request, as the tests do.
    recompute_in_background: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    debug: bool = False
    domain: str = "http://localhost:5173"
    # Two independent thresholds over the same records (see logger.py):
    # LOG_LEVEL throttles stdout, LOG_DB_LEVEL what reaches log_table and the
    # in-app Logs tab. The logger itself stays at DEBUG so either can be
    # lowered without the other.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"
    log_db_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Stdout line format (env LOG_FORMAT): "text" for humans, "json" for a
    # log aggregator (Loki/Elastic) to filter by rid/user/level.
    log_format: Literal["text", "json"] = "text"

    security: SecuritySettings
    database: DatabaseSettings
    redis: RedisSettings
    init: InitSettings
    local_storage: LocalStorageSettings = LocalStorageSettings()
    backup: BackupSettings = BackupSettings()
    scheduling: SchedulingSettings = SchedulingSettings()
    pdm: PdmSettings = PdmSettings()
    network: NetworkSettings = NetworkSettings()
    # The bundled SeaweedFS (compose profile `seaweedfs`) takes its S3 secret
    # from the same env file. The backend never connects with it, since the
    # storage settings hold their own copy; it reads the secret and
    # COMPOSE_PROFILES only so the boot guard can refuse a weak one.
    seaweedfs_secret_key: str = ""
    compose_profiles: str = ""


cfg = Settings()
