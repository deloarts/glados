"""
Shared identity fields for domain entities backed by a database row.
No SQLAlchemy, no Pydantic, no FastAPI, kept dependency-free like every
other file in this package.
"""

from dataclasses import dataclass
from dataclasses import field
from uuid import UUID
from uuid import uuid4


@dataclass(kw_only=True)
class Entity:
    id: int
    # Placeholder for not-yet-saved entities (id == 0); overwritten by the
    # real, DB-generated value once the repository's ORM->entity mapper
    # loads the persisted row. Never add this to a repository's
    # entity->dict update payload, that dict is shared between insert and
    # update, and doing so would rotate the value on every save. See the
    # matching note on Base.public_id in
    # src/modules/platform/adapters/outbound/persistence/models/base.py.
    public_id: UUID = field(default_factory=uuid4)
