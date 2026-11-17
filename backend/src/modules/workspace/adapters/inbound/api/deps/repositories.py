"""Repository factories on the request's session."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import repo_factory
from src.modules.workspace.adapters.outbound.persistence.repositories.contact_link_repository import (
    SqlAlchemyContactLinkRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_card_repository import (
    SqlAlchemyMeetingCardRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_file_repository import (
    SqlAlchemyMeetingFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notes_draft_repository import (
    SqlAlchemyMeetingNotesDraftRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notification_queue import (
    SqlAlchemyMeetingNotificationQueue,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_repository import (
    SqlAlchemyMeetingRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_snapshot_repository import (
    SqlAlchemyMeetingSnapshotRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.plc_environment_repository import (
    SqlAlchemyPlcEnvironmentRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.plc_manual_tag_repository import (
    SqlAlchemyPlcManualTagRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_check_repository import (
    SqlAlchemyProductDeviceCheckRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_repository import (
    SqlAlchemyProductDeviceRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_resource_repository import (
    SqlAlchemyProductDeviceKindRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_resource_repository import (
    SqlAlchemyProductDeviceOptionRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_file_repository import (
    SqlAlchemyProductFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_variant_repository import (
    SqlAlchemyProductVariantRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_notes_draft_repository import (
    IMeetingNotesDraftRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingCardRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingNotificationQueue,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import IMeetingRepository
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingSnapshotRepository,
)
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.plc_manual_tag_repository import (
    IPlcManualTagRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_check_repository import (
    IProductDeviceCheckRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceOptionRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_file_repository import (
    IProductFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.product_variant_repository import (
    IProductVariantRepository,
)
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository

get_contact_link_repo: Callable[[AsyncSession], IContactLinkRepository] = repo_factory(
    SqlAlchemyContactLinkRepository
)
get_product_repo: Callable[[AsyncSession], IProductRepository] = repo_factory(
    SqlAlchemyProductRepository
)
get_product_file_repo: Callable[[AsyncSession], IProductFileRepository] = repo_factory(
    SqlAlchemyProductFileRepository
)
get_project_repo: Callable[[AsyncSession], IProjectRepository] = repo_factory(
    SqlAlchemyProjectRepository
)
get_product_device_option_repo: Callable[[AsyncSession], IProductDeviceOptionRepository] = (
    repo_factory(SqlAlchemyProductDeviceOptionRepository)
)
get_product_device_kind_repo: Callable[[AsyncSession], IProductDeviceKindRepository] = repo_factory(
    SqlAlchemyProductDeviceKindRepository
)
get_product_device_repo: Callable[[AsyncSession], IProductDeviceRepository] = repo_factory(
    SqlAlchemyProductDeviceRepository
)
get_product_variant_repo: Callable[[AsyncSession], IProductVariantRepository] = repo_factory(
    SqlAlchemyProductVariantRepository
)
get_plc_environment_repo: Callable[[AsyncSession], IPlcEnvironmentRepository] = repo_factory(
    SqlAlchemyPlcEnvironmentRepository
)
get_plc_manual_tag_repo: Callable[[AsyncSession], IPlcManualTagRepository] = repo_factory(
    SqlAlchemyPlcManualTagRepository
)
get_product_device_check_repo: Callable[[AsyncSession], IProductDeviceCheckRepository] = (
    repo_factory(SqlAlchemyProductDeviceCheckRepository)
)
get_meeting_repo: Callable[[AsyncSession], IMeetingRepository] = repo_factory(
    SqlAlchemyMeetingRepository
)
get_meeting_card_repo: Callable[[AsyncSession], IMeetingCardRepository] = repo_factory(
    SqlAlchemyMeetingCardRepository
)
get_meeting_file_repo: Callable[[AsyncSession], IMeetingFileRepository] = repo_factory(
    SqlAlchemyMeetingFileRepository
)
get_meeting_notification_queue: Callable[[AsyncSession], IMeetingNotificationQueue] = repo_factory(
    SqlAlchemyMeetingNotificationQueue
)
get_meeting_notes_draft_repo: Callable[[AsyncSession], IMeetingNotesDraftRepository] = repo_factory(
    SqlAlchemyMeetingNotesDraftRepository
)
get_meeting_snapshot_repo: Callable[[AsyncSession], IMeetingSnapshotRepository] = repo_factory(
    SqlAlchemyMeetingSnapshotRepository
)
