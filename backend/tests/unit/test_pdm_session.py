"""
Unit tests for PdmSessionService against a fake repository and a fake
IPdmGateway: fresh login, token reuse, staleness-triggered re-login, the
401-retry-once path, and session clearing on an authentication failure.
No network, no real vault.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.errors import PdmNotConfiguredError
from src.modules.external_data.domain.errors import PdmSessionExpiredError
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection


def make_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = {
        "id": 1,
        "made_item_variable_map": {},
        "bought_item_variable_map": {},
        "enabled": False,
        "base_url": "http://pdm-host:65453",
        "vault_name": "MyVault",
        "username": "svc-account",
        "password": "secret",
        "verify_certificate": True,
        "timeout_seconds": 15,
        "session_token": None,
        "session_user_id": None,
        "session_obtained_at": None,
        "watched_folders": [],
        "made_released_state_ids": [],
        "made_obsolete_state_ids": [],
        "made_replaced_state_ids": [],
        "bought_released_state_ids": [],
        "bought_obsolete_state_ids": [],
        "bought_replaced_state_ids": [],
        "poll_interval_minutes": 15,
        "vault_id": "",
        "cad_items_read_only": True,
        "last_poll_at": None,
        "last_poll_error": None,
        "last_poll_summary": None,
        "writeback_enabled": False,
        "made_item_extensions": ["sldprt"],
        "bought_item_extensions": ["sldprt", "sldasm"],
        "document_categories": {"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        "thumbnails_enabled": False,
        "stuck_after_days": 7,
        "reconcile_requested_deep": None,
        "required_fields": {"made": [], "bought": []},
    }
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class FakeRepo:
    def __init__(self, settings: AdminPdmSettings) -> None:
        self.pdm = settings
        self.save_session_calls: list[dict[str, object]] = []

    async def get_pdm(self) -> AdminPdmSettings:
        return self.pdm

    async def save_pdm_session(
        self, *, token: str | None, user_id: int | None, obtained_at: datetime | None
    ) -> None:
        self.save_session_calls.append(
            {"token": token, "user_id": user_id, "obtained_at": obtained_at}
        )
        self.pdm.session_token = token
        self.pdm.session_user_id = user_id
        self.pdm.session_obtained_at = obtained_at


class FakeGateway:
    def __init__(self, auth_result: PdmAuthResult | Exception | None = None) -> None:
        self.auth_result = auth_result or PdmAuthResult(token="fresh-token", user_id=7)
        self.authenticate_calls = 0

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        self.authenticate_calls += 1
        if isinstance(self.auth_result, Exception):
            raise self.auth_result
        return self.auth_result

    # The rest of IPdmGateway is unused by PdmSessionService itself, `call`
    # only ever invokes the callback it is given.
    async def version(self) -> object:  # pragma: no cover - not exercised here
        raise NotImplementedError

    async def vault_info(self, token: str) -> object:  # pragma: no cover
        raise NotImplementedError

    async def search_files(self, token: str, query: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def files_info(self, token: str, file_ids: list[int]) -> object:  # pragma: no cover
        raise NotImplementedError

    async def file_info_from_path(self, token: str, path: str) -> object:  # pragma: no cover
        raise NotImplementedError

    async def browse_folder(self, token: str, folder_id: int) -> object:  # pragma: no cover
        raise NotImplementedError

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> object:  # pragma: no cover
        raise NotImplementedError

    async def workflows(self, token: str) -> object:  # pragma: no cover
        raise NotImplementedError

    async def get_datacard(self, token: str, file_id: int, version: int, folder_id: int) -> object:
        raise NotImplementedError  # pragma: no cover

    async def set_datacard_variables(
        self,
        token: str,
        file_id: int,
        folder_id: int,
        configuration_id: int,
        card: object,
        values: dict[str, str],
    ) -> bool:  # pragma: no cover
        raise NotImplementedError

    async def invoke(
        self,
        token: str | None,
        spec: object,
        path_params: object,
        query: object,
        body: object,
    ) -> object:  # pragma: no cover
        raise NotImplementedError


def make_service(repo: FakeRepo, gateway: FakeGateway) -> PdmSessionService:
    def factory(connection: PdmConnection) -> IPdmGateway:
        return gateway  # type: ignore[return-value]

    return PdmSessionService(repo=repo, gateway_factory=factory)  # type: ignore[arg-type]


async def _return_token(gw: IPdmGateway, token: str) -> str:
    return token


async def _unreachable(gw: IPdmGateway, token: str) -> str:
    return "unreachable"


# ── configuration guard ──────────────────────────────────────────────


async def test_raises_not_configured_when_settings_incomplete() -> None:
    repo = FakeRepo(make_settings(password=None))
    gateway = FakeGateway()
    service = make_service(repo, gateway)

    with pytest.raises(PdmNotConfiguredError):
        await service.call(_unreachable)

    assert gateway.authenticate_calls == 0


# ── login / reuse / staleness ────────────────────────────────────────


async def test_fresh_login_when_no_stored_token() -> None:
    repo = FakeRepo(make_settings())
    gateway = FakeGateway(PdmAuthResult(token="new-token", user_id=42))
    service = make_service(repo, gateway)

    result = await service.call(_return_token)

    assert result == "new-token"
    assert gateway.authenticate_calls == 1
    assert repo.pdm.session_token == "new-token"
    assert repo.pdm.session_user_id == 42
    assert repo.pdm.session_obtained_at is not None


async def test_reuses_stored_token_when_fresh() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="stored-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    gateway = FakeGateway()
    service = make_service(repo, gateway)

    result = await service.call(_return_token)

    assert result == "stored-token"
    assert gateway.authenticate_calls == 0


async def test_reauthenticates_when_stored_token_is_stale() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="old-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC) - timedelta(hours=25),
        )
    )
    gateway = FakeGateway(PdmAuthResult(token="refreshed-token", user_id=9))
    service = make_service(repo, gateway)

    result = await service.call(_return_token)

    assert result == "refreshed-token"
    assert gateway.authenticate_calls == 1
    assert repo.pdm.session_token == "refreshed-token"


# ── 401 retry-once path ──────────────────────────────────────────────


async def test_retries_once_on_session_expired_and_succeeds() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="expiring-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC),
        )
    )
    gateway = FakeGateway(PdmAuthResult(token="renewed-token", user_id=3))
    service = make_service(repo, gateway)

    seen_tokens: list[str] = []

    async def fn(gw: IPdmGateway, token: str) -> str:
        seen_tokens.append(token)
        if token == "expiring-token":
            raise PdmSessionExpiredError("token rejected")
        return token

    result = await service.call(fn)

    assert result == "renewed-token"
    assert seen_tokens == ["expiring-token", "renewed-token"]
    assert gateway.authenticate_calls == 1
    assert repo.pdm.session_token == "renewed-token"


async def test_second_session_expired_after_retry_propagates() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="expiring-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC),
        )
    )
    gateway = FakeGateway(PdmAuthResult(token="also-expiring", user_id=3))
    service = make_service(repo, gateway)

    async def fn(gw: IPdmGateway, token: str) -> str:
        raise PdmSessionExpiredError("token rejected")

    with pytest.raises(PdmSessionExpiredError):
        await service.call(fn)

    assert gateway.authenticate_calls == 1


async def test_retries_once_on_503_for_a_reused_token() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="dropped-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC),
        )
    )
    gateway = FakeGateway(PdmAuthResult(token="renewed-token", user_id=3))
    service = make_service(repo, gateway)

    seen_tokens: list[str] = []

    async def fn(gw: IPdmGateway, token: str) -> str:
        seen_tokens.append(token)
        if token == "dropped-token":
            raise PdmApiError("PDM call failed with HTTP 503.", status_code=503, body="")
        return token

    assert await service.call(fn) == "renewed-token"
    assert seen_tokens == ["dropped-token", "renewed-token"]
    assert gateway.authenticate_calls == 1
    assert repo.pdm.session_token == "renewed-token"


async def test_503_on_a_freshly_obtained_token_propagates() -> None:
    repo = FakeRepo(make_settings())
    gateway = FakeGateway(PdmAuthResult(token="fresh-token", user_id=3))
    service = make_service(repo, gateway)

    async def fn(gw: IPdmGateway, token: str) -> str:
        raise PdmApiError("PDM call failed with HTTP 503.", status_code=503, body="")

    with pytest.raises(PdmApiError):
        await service.call(fn)

    assert gateway.authenticate_calls == 1


async def test_other_status_on_a_reused_token_propagates_without_relogin() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="good-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC),
        )
    )
    gateway = FakeGateway(PdmAuthResult(token="unused", user_id=3))
    service = make_service(repo, gateway)

    async def fn(gw: IPdmGateway, token: str) -> str:
        raise PdmApiError("PDM call failed with HTTP 500.", status_code=500, body="")

    with pytest.raises(PdmApiError):
        await service.call(fn)

    assert gateway.authenticate_calls == 0


# ── authentication failure clears the stored session ────────────────


async def test_auth_failure_on_initial_login_clears_session() -> None:
    repo = FakeRepo(make_settings())
    gateway = FakeGateway(PdmAuthenticationFailedError("rejected"))
    service = make_service(repo, gateway)

    with pytest.raises(PdmAuthenticationFailedError):
        await service.call(_unreachable)

    assert repo.save_session_calls[-1] == {
        "token": None,
        "user_id": None,
        "obtained_at": None,
    }
    assert repo.pdm.session_token is None


async def test_auth_failure_on_retry_clears_session() -> None:
    repo = FakeRepo(
        make_settings(
            session_token="expiring-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC),
        )
    )
    gateway = FakeGateway()
    service = make_service(repo, gateway)

    async def fn(gw: IPdmGateway, token: str) -> str:
        raise PdmSessionExpiredError("token rejected")

    # Swap in a rejecting gateway only once the retry's re-authenticate runs.
    async def failing_authenticate(username: str, password: str) -> PdmAuthResult:
        raise PdmAuthenticationFailedError("rejected on retry")

    gateway.authenticate = failing_authenticate  # type: ignore[method-assign]

    with pytest.raises(PdmAuthenticationFailedError):
        await service.call(fn)

    assert repo.pdm.session_token is None


# ── connection release before every Web API request ─────────────────


class _OrderedUow:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def commit(self) -> None:
        self._events.append("commit")

    async def rollback(self) -> None:  # pragma: no cover - never called by the service
        self._events.append("rollback")


class _OrderedGateway(FakeGateway):
    def __init__(self, events: list[str]) -> None:
        super().__init__(PdmAuthResult(token="fresh-token", user_id=7))
        self._events = events

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        self._events.append("authenticate")
        return await super().authenticate(username, password)


def _make_ordered_service(
    repo: FakeRepo, events: list[str]
) -> tuple[PdmSessionService, _OrderedGateway]:
    gateway = _OrderedGateway(events)

    def factory(connection: PdmConnection) -> IPdmGateway:
        return gateway  # type: ignore[return-value]

    service = PdmSessionService(
        repo=repo,  # type: ignore[arg-type]
        gateway_factory=factory,
        uow=_OrderedUow(events),
    )
    return service, gateway


async def test_commits_before_running_fn_with_a_reused_token() -> None:
    events: list[str] = []
    repo = FakeRepo(
        make_settings(
            session_token="stored-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    service, _ = _make_ordered_service(repo, events)

    async def fn(gw: IPdmGateway, token: str) -> str:
        events.append("fn")
        return token

    assert await service.call(fn) == "stored-token"
    assert events == ["commit", "fn"]


async def test_commits_before_authenticating_and_again_before_fn() -> None:
    events: list[str] = []
    repo = FakeRepo(make_settings())
    service, _ = _make_ordered_service(repo, events)

    async def fn(gw: IPdmGateway, token: str) -> str:
        events.append("fn")
        return token

    assert await service.call(fn) == "fresh-token"
    assert events == ["commit", "authenticate", "commit", "fn"]


async def test_commits_before_the_retry_login_and_the_retried_fn() -> None:
    events: list[str] = []
    repo = FakeRepo(
        make_settings(
            session_token="stored-token",
            session_user_id=1,
            session_obtained_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    service, _ = _make_ordered_service(repo, events)
    attempts = 0

    async def fn(gw: IPdmGateway, token: str) -> str:
        nonlocal attempts
        attempts += 1
        events.append("fn")
        if attempts == 1:
            raise PdmSessionExpiredError("expired")
        return token

    assert await service.call(fn) == "fresh-token"
    assert events == ["commit", "fn", "commit", "authenticate", "commit", "fn"]


async def test_without_a_unit_of_work_nothing_is_committed() -> None:
    repo = FakeRepo(make_settings())
    gateway = FakeGateway()
    service = make_service(repo, gateway)

    assert await service.call(_return_token) == "fresh-token"
    assert gateway.authenticate_calls == 1
