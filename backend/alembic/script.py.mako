"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
<%!
    def quoted(value):
        """Renders a revision id in the double quotes ruff formats strings with."""
        return f'"{value}"' if isinstance(value, str) else repr(value)
%>
from collections.abc import Sequence

import sqlalchemy as sa
% if imports:
${imports}
% endif

from alembic import op

# revision identifiers, used by Alembic.
revision: str = ${quoted(up_revision)}
down_revision: str | None = ${quoted(down_revision)}
branch_labels: str | Sequence[str] | None = ${quoted(branch_labels)}
depends_on: str | Sequence[str] | None = ${quoted(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
