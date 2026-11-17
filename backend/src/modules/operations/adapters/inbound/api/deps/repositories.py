"""Repository factories on the request's session, and the module's settings
store."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.operations.adapters.outbound.persistence.repositories.infoscreen_repository import (
    SqlAlchemyInfoscreenRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.operations_settings_repository import (
    SqlAlchemyOperationsSettingsRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.terminal_broadcast_repository import (
    SqlAlchemyTerminalBroadcastRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.terminal_repository import (
    SqlAlchemyTerminalRepository,
)
from src.modules.operations.adapters.outbound.persistence.repositories.time_tracking_credentials_repository import (
    SqlAlchemyUserTimeTrackingCredentialsRepository,
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
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory

get_user_time_tracking_credentials_repo: Callable[
    [AsyncSession], IUserTimeTrackingCredentialsRepository
] = repo_factory(SqlAlchemyUserTimeTrackingCredentialsRepository)
get_terminal_repo: Callable[[AsyncSession], ITerminalRepository] = repo_factory(
    SqlAlchemyTerminalRepository
)
get_infoscreen_repo: Callable[[AsyncSession], IInfoscreenRepository] = repo_factory(
    SqlAlchemyInfoscreenRepository
)
get_terminal_broadcast_repo: Callable[[AsyncSession], ITerminalBroadcastRepository] = repo_factory(
    SqlAlchemyTerminalBroadcastRepository
)

get_operations_settings_repo: Callable[[AsyncSession], IOperationsSettingsRepository] = (
    repo_factory(SqlAlchemyOperationsSettingsRepository)
)
