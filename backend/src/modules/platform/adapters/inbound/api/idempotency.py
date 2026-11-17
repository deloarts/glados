"""
The Idempotency-Key header of the routes whose repetition would book
something twice (application/services/idempotency.py). A web route takes the
`get_idempotency` dependency, a pat route `get_pat_idempotency`, and runs
its write through `Idempotency.run`,
naming the resources the write produced and how to answer a replay from
them. A request without the header runs as before. The use case's commits
are held back while it runs, so what it wrote and the key's record of it
commit in one transaction.

The request hash covers the method, the path, the query parameters in
order of their names and the raw body, so a key sent again with any other
request is told apart from a retry.
"""

import hashlib
from collections.abc import Awaitable
from collections.abc import Callable

from fastapi import Depends
from fastapi import Header
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_idempotency_key_repo
from src.modules.platform.adapters.outbound.persistence.unit_of_work import hold_commits
from src.modules.platform.application.services.idempotency import IdempotencyKeys
from src.modules.platform.application.services.idempotency import IdempotentRequest
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.idempotency_key_repository import (
    IIdempotencyKeyRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

IDEMPOTENCY_HEADER = "Idempotency-Key"


class Idempotency:
    def __init__(
        self, keys: IdempotencyKeys, request: IdempotentRequest | None, session: AsyncSession
    ) -> None:
        self._keys = keys
        self._request = request
        self._session = session

    async def run[T](
        self,
        write: Callable[[], Awaitable[T]],
        *,
        written: Callable[[T], list[ResourceRef]],
        replay: Callable[[tuple[ResourceRef, ...]], Awaitable[T]],
    ) -> T:
        """Runs `write` once per key: the first request writes and records
        `written(result)`, a retry is answered by `replay` from those
        resources without writing again. The commits of `write` are held
        back (hold_commits), so the work, the key and the record of what it
        wrote commit together, and a booked request never leaves its key
        open."""
        if self._request is None:
            return await write()
        claim = await self._keys.claim(self._request)
        if claim.replay is not None:
            return await replay(claim.replay)
        async with hold_commits(self._session):
            result = await write()
        await self._keys.complete(claim, written(result))
        return result


async def _request_hash(request: Request) -> str:
    digest = hashlib.sha256()
    digest.update(request.method.encode())
    digest.update(b"\n" + request.url.path.encode())
    for name, value in sorted(request.query_params.multi_items()):
        digest.update(b"\n" + name.encode() + b"=" + value.encode())
    digest.update(b"\n" + await request.body())
    return digest.hexdigest()


_KEY_DESCRIPTION = (
    "A key the client generates per user action and sends again on a retry, so the "
    "request is booked once; a retry is answered from what the first one wrote."
)


async def get_idempotency(
    request: Request,
    key: str | None = Header(default=None, alias=IDEMPOTENCY_HEADER, description=_KEY_DESCRIPTION),
    actor: User = Depends(get_current_active_user),
    repo: IIdempotencyKeyRepository = Depends(get_idempotency_key_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> Idempotency:
    return await _idempotency(request, key, actor, repo, uow, db)


async def get_pat_idempotency(
    request: Request,
    key: str | None = Header(default=None, alias=IDEMPOTENCY_HEADER, description=_KEY_DESCRIPTION),
    actor: User = Depends(get_current_user_pat),
    repo: IIdempotencyKeyRepository = Depends(get_idempotency_key_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> Idempotency:
    """The same for a pat route, whose caller is the token's user. A key is
    the user's, so the same key from the web and from a token is one key."""
    return await _idempotency(request, key, actor, repo, uow, db)


async def _idempotency(
    request: Request,
    key: str | None,
    actor: User,
    repo: IIdempotencyKeyRepository,
    uow: IUnitOfWork,
    db: AsyncSession,
) -> Idempotency:
    keys = IdempotencyKeys(repo, uow=uow)
    if key is None:
        return Idempotency(keys, None, db)
    route = request.scope.get("route")
    template = getattr(route, "path", request.url.path)
    return Idempotency(
        keys,
        IdempotentRequest(
            user_id=actor.id,
            key=key,
            route=f"{request.method} {template}",
            request_hash=await _request_hash(request),
        ),
        db,
    )
