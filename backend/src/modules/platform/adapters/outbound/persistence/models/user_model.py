"""
SQLAlchemy ORM model. Infrastructure detail, never imported by domain or application.
No config imports. Default values are plain constants from const.py.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.const import SERVER_DEFAULT_AUTH_PROVIDER
from src.modules.platform.const import SERVER_DEFAULT_BUTTON_FLAT_STYLE
from src.modules.platform.const import SERVER_DEFAULT_DATE_FORMAT
from src.modules.platform.const import SERVER_DEFAULT_LANGUAGE
from src.modules.platform.const import SERVER_DEFAULT_START_PAGE
from src.modules.platform.const import SERVER_DEFAULT_TABLE_GRIDLINES
from src.modules.platform.const import SERVER_DEFAULT_TABLE_STRIPED_ROWS
from src.modules.platform.const import SERVER_DEFAULT_THEME_DARK_MODE
from src.modules.platform.const import SERVER_DEFAULT_THEME_PRESET
from src.modules.platform.const import SERVER_DEFAULT_THEME_PRIMARY
from src.modules.platform.const import SERVER_DEFAULT_THEME_SURFACE

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_group_model import (
        UserGroupOrmModel,
    )

# Many-to-many, self-referential: which real-person users are eligible
# operators for a given shared account.
shared_account_member_table = sa.Table(
    "shared_account_member_table",
    Base.metadata,
    sa.Column(
        "shared_account_id",
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_shared_account_member_shared_account_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    sa.Column(
        "member_id",
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_shared_account_member_member_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        index=True,
    ),
)


class UserOrmModel(Base):
    __tablename__ = "user_table"

    # rfid_lookup uniqueness is scoped to non-null rows. Postgres already
    # allows multiple NULLs through a plain UNIQUE column, but the partial
    # index is explicit about the intent and keeps the users without a tag
    # out of the index. See infrastructure/security/rfid.py for what the
    # value is.
    #
    # At most one row carries is_systemuser: the flag grants every
    # permission, so a second flagged row would be a full bypass.
    # init_db._ensure_system_user creates and re-syncs that one `system`
    # row, and no command can set the flag.
    __table_args__ = (
        sa.Index(
            "uq_user_rfid_lookup_active",
            "rfid_lookup",
            unique=True,
            postgresql_where=sa.text("rfid_lookup IS NOT NULL"),
            sqlite_where=sa.text("rfid_lookup IS NOT NULL"),
        ),
        sa.Index(
            "uq_user_single_systemuser",
            "is_systemuser",
            unique=True,
            postgresql_where=sa.text("is_systemuser IS true"),
            sqlite_where=sa.text("is_systemuser = 1"),
        ),
    )

    # Server-managed
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_logged_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When a password login last proved the password, see User.password_verified_at.
    password_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Identity
    username: Mapped[str] = mapped_column(String, index=True, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    rfid_lookup: Mapped[str | None] = mapped_column(String, nullable=True)

    # Preferences
    language: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_LANGUAGE
    )
    # DateFormat preset, display-only.
    date_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_DATE_FORMAT
    )
    # StartPage value, where this user lands right after login. Per-user
    # only, no tenant-wide default column, see StartPage's docstring.
    start_page: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_START_PAGE
    )
    theme_preset: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_THEME_PRESET
    )
    theme_surface: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_THEME_SURFACE
    )
    theme_primary: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_THEME_PRIMARY
    )
    theme_dark_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=SERVER_DEFAULT_THEME_DARK_MODE, server_default="true"
    )
    button_flat_style: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=SERVER_DEFAULT_BUTTON_FLAT_STYLE, server_default="false"
    )
    table_gridlines: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=SERVER_DEFAULT_TABLE_GRIDLINES, server_default="false"
    )
    table_striped_rows: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=SERVER_DEFAULT_TABLE_STRIPED_ROWS, server_default="false"
    )

    # Role flags
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_systemuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_service_account: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_shared_account: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Authentication
    auth_provider: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_AUTH_PROVIDER
    )

    # Permissions
    permissions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    # 2FA
    # Encrypted rather than hashed: the TOTP secret MUST stay recoverable to
    # compute the comparison code on every verification. Never echoed by the
    # API (see UserResult).
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Avatar
    avatar_key: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relations
    # Operators eligible to act under this shared account (self-referential
    # many-to-many; empty for personal accounts).
    members: Mapped[list["UserOrmModel"]] = relationship(
        "UserOrmModel",
        secondary=shared_account_member_table,
        primaryjoin=lambda: UserOrmModel.id == shared_account_member_table.c.shared_account_id,
        secondaryjoin=lambda: UserOrmModel.id == shared_account_member_table.c.member_id,
        # Loaded explicitly like every other relationship (user_load_options
        # and the `.selectinload(UserOrmModel.members)` on every loader that
        # reaches a user): a default eager loader does not refresh a user
        # already in the session, which surfaced as an implicit load.
        lazy="raise_on_sql",
    )
    # The groups this user belongs to. Only the user repository loads them,
    # every other loader that reaches a user leaves them alone (see
    # User.group_ids).
    groups: Mapped[list["UserGroupOrmModel"]] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_group_model.UserGroupOrmModel",
        secondary="user_group_member_table",
        back_populates="members",
        # The membership table cascades on delete, so removing a row never
        # needs this collection loaded.
        passive_deletes=True,
        lazy="raise_on_sql",
    )
