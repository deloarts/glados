"""Use-case factories for terminals, the device sign-in, terminal keys and
infoscreens, plus the loader a terminal's live stream uses to re-read its
scope outside the request's session.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_item_picture_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_file_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemFileQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_calendar_repo
from src.modules.operations.adapters.inbound.api.deps.bindings import get_infoscreen_feed_builder
from src.modules.operations.adapters.inbound.api.deps.repositories import get_infoscreen_repo
from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_operations_settings_repo,
)
from src.modules.operations.adapters.inbound.api.deps.repositories import (
    get_terminal_broadcast_repo,
)
from src.modules.operations.adapters.inbound.api.deps.repositories import get_terminal_repo
from src.modules.operations.adapters.inbound.api.deps.services import get_terminal_auth_rate_limiter
from src.modules.operations.adapters.outbound.external.weather.service import get_weather_service
from src.modules.operations.adapters.outbound.persistence.repositories.terminal_repository import (
    SqlAlchemyTerminalRepository,
)
from src.modules.operations.application.services.display_calendar import DisplayCalendarReader
from src.modules.operations.application.services.infoscreen_feed_builder import (
    IInfoscreenFeedBuilder,
)
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.operations.application.services.terminal_device_state import (
    TerminalDeviceStateReader,
)
from src.modules.operations.application.use_cases.infoscreen.display_schedule_default import (
    GetDisplayScheduleDefault,
)
from src.modules.operations.application.use_cases.infoscreen.display_schedule_default import (
    SetDisplayScheduleDefault,
)
from src.modules.operations.application.use_cases.infoscreen.get_infoscreen_feed import (
    GetInfoscreenFeed,
)
from src.modules.operations.application.use_cases.infoscreen.get_infoscreen_feed import (
    GetTerminalFeed,
)
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import CreateInfoscreen
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import GetInfoscreen
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import GetInfoscreens
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import (
    SetInfoscreenArchived,
)
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import UpdateInfoscreen
from src.modules.operations.application.use_cases.infoscreen.search_weather_places import (
    SearchWeatherPlaces,
)
from src.modules.operations.application.use_cases.infoscreen.serve_drawing import (
    ServeInfoscreenDrawing,
)
from src.modules.operations.application.use_cases.infoscreen.serve_thumbnail import (
    ServeInfoscreenThumbnail,
)
from src.modules.operations.application.use_cases.terminal.create_terminal_key import (
    CreateTerminalKey,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import ApproveTerminal
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    ClearTerminalDisplayOverride,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import DeleteTerminal
from src.modules.operations.application.use_cases.terminal.terminal_admin import ListTerminals
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    RequestTerminalIdentify,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    RequestTerminalReload,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import RevokeTerminal
from src.modules.operations.application.use_cases.terminal.terminal_admin import (
    SetTerminalDisplayOverride,
)
from src.modules.operations.application.use_cases.terminal.terminal_admin import UpdateTerminal
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    CountTerminalBroadcastReach,
)
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    EndTerminalBroadcast,
)
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    ListActiveTerminalBroadcasts,
)
from src.modules.operations.application.use_cases.terminal.terminal_broadcasts import (
    SendTerminalBroadcast,
)
from src.modules.operations.application.use_cases.terminal.terminal_bulk import DeleteAllTerminals
from src.modules.operations.application.use_cases.terminal.terminal_bulk import IdentifyAllTerminals
from src.modules.operations.application.use_cases.terminal.terminal_bulk import ReloadAllTerminals
from src.modules.operations.application.use_cases.terminal.terminal_bulk import RevokeAllTerminals
from src.modules.operations.application.use_cases.terminal_device.get_device_state import (
    GetTerminalDeviceState,
)
from src.modules.operations.application.use_cases.terminal_device.get_live_scope import (
    GetTerminalLiveScope,
)
from src.modules.operations.application.use_cases.terminal_device.get_live_scope import (
    TerminalLiveScope,
)
from src.modules.operations.application.use_cases.terminal_device.issue_challenge import (
    IssueTerminalChallenge,
)
from src.modules.operations.application.use_cases.terminal_device.start_session import (
    StartTerminalSession,
)
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_broadcast_repository import (
    ITerminalBroadcastRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_api_key_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.api import ITenantHolidayRepository
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

TerminalLiveScopeLoader = Callable[[int], Awaitable[TerminalLiveScope | None]]

# ── Display power and device state ────────────────────────────────────


def get_display_calendar_reader(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    holiday_repo: ITenantHolidayRepository = Depends(get_machine_calendar_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
) -> DisplayCalendarReader:
    return DisplayCalendarReader(
        settings_repo=settings_repo, holiday_repo=holiday_repo, infoscreen_repo=infoscreen_repo
    )


def get_terminal_device_state_reader(
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    broadcast_repo: ITerminalBroadcastRepository = Depends(get_terminal_broadcast_repo),
) -> TerminalDeviceStateReader:
    return TerminalDeviceStateReader(calendar=calendar, broadcast_repo=broadcast_repo)


def get_terminal_device_state_use_case(
    state_reader: TerminalDeviceStateReader = Depends(get_terminal_device_state_reader),
) -> GetTerminalDeviceState:
    return GetTerminalDeviceState(state_reader)


# ── Device sign-in ────────────────────────────────────────────────────


def get_issue_terminal_challenge_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    rate_limiter: TerminalAuthRateLimiter = Depends(get_terminal_auth_rate_limiter),
) -> IssueTerminalChallenge:
    return IssueTerminalChallenge(settings_repo=settings_repo, rate_limiter=rate_limiter)


def get_start_terminal_session_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    replay_guard: IReplayGuard = Depends(get_replay_guard),
    rate_limiter: TerminalAuthRateLimiter = Depends(get_terminal_auth_rate_limiter),
    state_reader: TerminalDeviceStateReader = Depends(get_terminal_device_state_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> StartTerminalSession:
    return StartTerminalSession(
        terminal_repo=terminal_repo,
        settings_repo=settings_repo,
        key_repo=key_repo,
        user_repo=user_repo,
        replay_guard=replay_guard,
        rate_limiter=rate_limiter,
        state_reader=state_reader,
        uow=uow,
    )


async def _load_terminal_live_scope(terminal_id: int) -> TerminalLiveScope | None:
    """Opens its own short session: a live stream outlives the request's."""
    async with SessionLocal() as db:
        return await GetTerminalLiveScope(SqlAlchemyTerminalRepository(db)).execute(terminal_id)


def get_terminal_live_scope_loader() -> TerminalLiveScopeLoader:
    return _load_terminal_live_scope


def get_serve_infoscreen_thumbnail_use_case(
    picture_repo: IItemPictureQueries = Depends(get_item_picture_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ServeInfoscreenThumbnail:
    return ServeInfoscreenThumbnail(
        picture_repo=picture_repo,
        item_repos={
            ItemKind.MADE: made_item_repo,
            ItemKind.BOUGHT: bought_item_repo,
            ItemKind.SOURCE: source_item_repo,
        },
        storage=storage,
        uow=uow,
    )


def get_serve_infoscreen_drawing_use_case(
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    file_repo: IMadeItemFileQueries = Depends(get_made_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ServeInfoscreenDrawing:
    return ServeInfoscreenDrawing(
        made_item_repo=made_item_repo, file_repo=file_repo, storage=storage, uow=uow
    )


def get_infoscreen_feed_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    builder: IInfoscreenFeedBuilder = Depends(get_infoscreen_feed_builder),
    broadcast_repo: ITerminalBroadcastRepository = Depends(get_terminal_broadcast_repo),
) -> GetInfoscreenFeed:
    return GetInfoscreenFeed(
        infoscreen_repo=infoscreen_repo, builder=builder, broadcast_repo=broadcast_repo
    )


def get_terminal_feed_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    builder: IInfoscreenFeedBuilder = Depends(get_infoscreen_feed_builder),
    broadcast_repo: ITerminalBroadcastRepository = Depends(get_terminal_broadcast_repo),
) -> GetTerminalFeed:
    return GetTerminalFeed(
        infoscreen_repo=infoscreen_repo, builder=builder, broadcast_repo=broadcast_repo
    )


# ── Terminal keys ─────────────────────────────────────────────────────


def get_create_terminal_key_use_case(
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    audit: SecurityAudit = Depends(get_security_audit),
) -> CreateTerminalKey:
    return CreateTerminalKey(
        key_repo=key_repo,
        user_repo=user_repo,
        uow=uow,
        settings_repo=settings_repo,
        hash_password_fn=aget_hash,
        audit=audit,
    )


# ── Admin terminals ───────────────────────────────────────────────────


def get_list_terminals_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
) -> ListTerminals:
    return ListTerminals(terminal_repo, calendar)


def get_approve_terminal_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ApproveTerminal:
    return ApproveTerminal(terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow)


def get_update_terminal_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateTerminal:
    return UpdateTerminal(terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow)


def get_revoke_terminal_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RevokeTerminal:
    return RevokeTerminal(terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow)


def get_request_terminal_reload_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RequestTerminalReload:
    return RequestTerminalReload(terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow)


def get_request_terminal_identify_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RequestTerminalIdentify:
    return RequestTerminalIdentify(terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow)


def get_set_terminal_display_override_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetTerminalDisplayOverride:
    return SetTerminalDisplayOverride(
        terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow
    )


def get_clear_terminal_display_override_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ClearTerminalDisplayOverride:
    return ClearTerminalDisplayOverride(
        terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow
    )


def get_delete_terminal_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    calendar: DisplayCalendarReader = Depends(get_display_calendar_reader),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteTerminal:
    return DeleteTerminal(terminal_repo, infoscreen_repo, settings_repo, calendar, uow=uow)


def get_reload_all_terminals_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ReloadAllTerminals:
    return ReloadAllTerminals(terminal_repo, settings_repo, uow=uow)


def get_identify_all_terminals_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> IdentifyAllTerminals:
    return IdentifyAllTerminals(terminal_repo, settings_repo, uow=uow)


def get_revoke_all_terminals_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RevokeAllTerminals:
    return RevokeAllTerminals(terminal_repo, settings_repo, uow=uow)


def get_delete_all_terminals_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteAllTerminals:
    return DeleteAllTerminals(terminal_repo, settings_repo, uow=uow)


# ── Messages to terminals ─────────────────────────────────────────────


def get_list_active_terminal_broadcasts_use_case(
    broadcast_repo: ITerminalBroadcastRepository = Depends(get_terminal_broadcast_repo),
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
) -> ListActiveTerminalBroadcasts:
    return ListActiveTerminalBroadcasts(broadcast_repo, terminal_repo)


def get_count_terminal_broadcast_reach_use_case(
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
) -> CountTerminalBroadcastReach:
    return CountTerminalBroadcastReach(terminal_repo)


def get_send_terminal_broadcast_use_case(
    broadcast_repo: ITerminalBroadcastRepository = Depends(get_terminal_broadcast_repo),
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SendTerminalBroadcast:
    return SendTerminalBroadcast(
        broadcast_repo, terminal_repo, infoscreen_repo, settings_repo, uow=uow
    )


def get_end_terminal_broadcast_use_case(
    broadcast_repo: ITerminalBroadcastRepository = Depends(get_terminal_broadcast_repo),
    terminal_repo: ITerminalRepository = Depends(get_terminal_repo),
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> EndTerminalBroadcast:
    return EndTerminalBroadcast(broadcast_repo, terminal_repo, settings_repo, uow=uow)


# ── Infoscreens ───────────────────────────────────────────────────────


def get_infoscreens_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
) -> GetInfoscreens:
    return GetInfoscreens(infoscreen_repo)


def get_infoscreen_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
) -> GetInfoscreen:
    return GetInfoscreen(infoscreen_repo)


def get_create_infoscreen_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateInfoscreen:
    return CreateInfoscreen(infoscreen_repo, uow=uow)


def get_update_infoscreen_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateInfoscreen:
    return UpdateInfoscreen(infoscreen_repo, uow=uow)


def get_display_schedule_default_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
) -> GetDisplayScheduleDefault:
    return GetDisplayScheduleDefault(infoscreen_repo)


def get_set_display_schedule_default_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetDisplayScheduleDefault:
    return SetDisplayScheduleDefault(infoscreen_repo, uow=uow)


def get_set_infoscreen_archived_use_case(
    infoscreen_repo: IInfoscreenRepository = Depends(get_infoscreen_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetInfoscreenArchived:
    return SetInfoscreenArchived(infoscreen_repo, uow=uow)


def get_search_weather_places_use_case(
    settings_repo: IOperationsSettingsRepository = Depends(get_operations_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SearchWeatherPlaces:
    return SearchWeatherPlaces(weather=get_weather_service(), settings_repo=settings_repo, uow=uow)
