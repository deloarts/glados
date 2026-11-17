"""
Registers each module's contributions with the Platform registries, so
Platform code that serves every module, such as the event codec, never
names a module itself. Every process entry point calls `register_all`
before it handles a request, an event or a command: the app factory, the
CLI and the test session.
"""

from src.bootstrap.bindings import bind_request_dependencies
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
    BoughtItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.contact_model import ContactOrmModel
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.item_picture_model import (
    ItemPictureOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemCreated
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemStatusChanged
from src.modules.catalogue.domain.events.bought_item_events import DemandItemCreated
from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemCreated
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemCreated
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemStatusChanged
from src.modules.catalogue.domain.events.source_item_events import SourceItemStatusChanged
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.domain.events.pdm_events import PdmFileIngested
from src.modules.external_data.domain.events.pdm_events import PdmIngestConflict
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
    MachinePoolOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
    ProductionMachineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineDemandOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestSupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.application.use_cases._demand_family.notifications import (
    DEMAND_NOTIFICATION_RULES,
)
from src.modules.fulfillment.application.use_cases.order.notifications import (
    ORDER_NOTIFICATION_RULES,
)
from src.modules.fulfillment.application.use_cases.production_lot.notifications import (
    LOT_NOTIFICATION_RULES,
)
from src.modules.fulfillment.domain.events.lot_events import LotCanceled
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.events.lot_events import LotEndedShort
from src.modules.fulfillment.domain.events.lot_events import LotOnHold
from src.modules.fulfillment.domain.events.lot_events import LotPositionAssigned
from src.modules.fulfillment.domain.events.lot_events import LotPositionDeliveryRecorded
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotResumed
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeEnded
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeStarted
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolArchived
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolCreated
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolRestored
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolUpdated
from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.events.order_events import OrderCanceled
from src.modules.fulfillment.domain.events.order_events import OrderCreated
from src.modules.fulfillment.domain.events.order_events import OrderItemDelivered
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderRequested
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderSubmitted
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineArchived,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineCreated
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineRestored,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineUpdated
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionRecorded,
)
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionReversed,
)
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderPaused
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderResumed
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderStarted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.events.quote_request_events import QuoteRequestStatusChanged
from src.modules.fulfillment.domain.events.schedule_events import ScheduleRecomputeRequested
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.operations.adapters.outbound.persistence.models.infoscreen_model import (
    InfoscreenDisplayDefaultOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.models.infoscreen_model import (
    InfoscreenOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.models.terminal_broadcast_model import (
    TerminalBroadcastOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.models.terminal_model import (
    TerminalOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.change_tracking import LiveTopic
from src.modules.platform.adapters.outbound.persistence.change_tracking import register_live_topics
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementRecipientOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.banner import (
    AdminBannerSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.public_id_lookup import (
    register_public_id_models,
)
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    register_notification_rules,
)
from src.modules.platform.domain.events.user_events import UserDeactivated
from src.modules.platform.domain.events.user_events import UserForcedLogout
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.infrastructure.events.registry import register_events
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.quality.adapters.outbound.persistence.models.calculation_model import (
    CalculationOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.models.checklist_model import (
    ChecklistOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.models.printer_model import PrinterOrmModel
from src.modules.quality.adapters.outbound.persistence.models.sequence_model import SequenceOrmModel
from src.modules.quality.application.use_cases._controlled_documents.notifications import (
    DOCUMENT_NOTIFICATION_RULES,
)
from src.modules.quality.domain.events.document_events import DocumentEditingEnded
from src.modules.quality.domain.events.document_events import DocumentEditingTakenOver
from src.modules.quality.domain.events.document_events import DocumentMarkedInvalid
from src.modules.quality.domain.events.document_events import DocumentRevised
from src.modules.quality.domain.events.printer_events import PrinterArchived
from src.modules.quality.domain.events.printer_events import PrinterCreated
from src.modules.quality.domain.events.printer_events import PrinterRestored
from src.modules.quality.domain.events.printer_events import PrinterUpdated
from src.modules.workspace.adapters.outbound.persistence.models.contact_link_model import (
    ProductContactOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.contact_link_model import (
    ProjectContactOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingAttendeeOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingCardOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingDecisionOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingFileOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import MeetingOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTagOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingTodoOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceComponentOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
    ProductDeviceOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.application.use_cases.meeting.notifications import (
    MEETING_NOTIFICATION_RULES,
)
from src.modules.workspace.application.use_cases.product.notifications import (
    PRODUCT_NOTIFICATION_RULES,
)
from src.modules.workspace.application.use_cases.project.notifications import (
    PROJECT_NOTIFICATION_RULES,
)
from src.modules.workspace.domain.events.meeting_events import MeetingActivityDue
from src.modules.workspace.domain.events.product_events import ProductCreated
from src.modules.workspace.domain.events.product_events import ProductUpdated
from src.modules.workspace.domain.events.project_events import ProjectCreated
from src.modules.workspace.domain.events.project_events import ProjectDeleted
from src.modules.workspace.domain.events.project_events import ProjectUpdated

_registered = False


def register_all() -> None:
    """Registers everything once per process; later calls do nothing."""
    global _registered
    if _registered:
        return
    _registered = True
    register_events(
        BoughtItemCreated,
        BoughtItemEdpPictureRequested,
        BoughtItemStatusChanged,
        DemandItemCreated,
        DemandItemStatusChanged,
        MadeItemCreated,
        MadeItemStatusChanged,
        MadeItemDemandItemCreated,
        MadeItemDemandItemStatusChanged,
        SourceItemStatusChanged,
        SourceItemDemandStatusChanged,
        OrderCreated,
        OrderRequested,
        OrderSubmitted,
        OrderCanceled,
        OrderItemDelivered,
        DeliveryPiecesRejected,
        OrderStatusChanged,
        OrderItemStatusChanged,
        LotCreated,
        LotCompleted,
        LotCanceled,
        LotEndedShort,
        LotSupplierLinesToSettle,
        ScheduleRecomputeRequested,
        LotPositionAssigned,
        LotPositionDeliveryRecorded,
        LotOnHold,
        LotResumed,
        LotStatusChanged,
        LotPositionStatusChanged,
        PiecesScrapped,
        ProductCreated,
        ProductUpdated,
        ProductionMachineCreated,
        ProductionMachineUpdated,
        ProductionMachineArchived,
        ProductionMachineRestored,
        MachinePoolCreated,
        MachinePoolUpdated,
        MachinePoolArchived,
        MachinePoolRestored,
        MachineDowntimeStarted,
        MachineDowntimeEnded,
        ProductionOrderCreated,
        ProductionOrderStarted,
        ProductionOrderPaused,
        ProductionOrderResumed,
        ProductionOrderCompletionRecorded,
        ProductionOrderCompletionReversed,
        ProductionOrderCompleted,
        ProductionOrderCanceled,
        ProductionOrderStatusChanged,
        QuoteRequestStatusChanged,
        ProjectCreated,
        MeetingActivityDue,
        ProjectUpdated,
        ProjectDeleted,
        PrinterCreated,
        PrinterUpdated,
        PrinterArchived,
        PrinterRestored,
        UserPermissionsChanged,
        UserDeactivated,
        UserForcedLogout,
        DocumentEditingTakenOver,
        DocumentEditingEnded,
        DocumentMarkedInvalid,
        DocumentRevised,
        PdmFileChangeRequested,
        PdmFileIngested,
        PdmIngestConflict,
    )
    register_public_id_models(
        {
            ProductOrmModel: LiveResource.PRODUCTS,
            CustomerOrmModel: LiveResource.CUSTOMERS,
            ProjectOrmModel: LiveResource.PROJECTS,
            SupplierOrmModel: LiveResource.SUPPLIERS,
            ArticleGroupOrmModel: LiveResource.ARTICLE_GROUPS,
            FabricationMethodOrmModel: LiveResource.FABRICATION_METHODS,
            SourceItemTypeOrmModel: LiveResource.SOURCE_ITEM_TYPES,
            SourceItemOrmModel: LiveResource.SOURCE_ITEMS,
            BoughtItemOrmModel: LiveResource.BOUGHT_ITEMS,
            MadeItemOrmModel: LiveResource.MADE_ITEMS,
            OrderOrmModel: LiveResource.ORDERS,
            ProductionLotOrmModel: LiveResource.PRODUCTION_LOTS,
            ProductionMachineOrmModel: LiveResource.PRODUCTION_MACHINES,
            MachinePoolOrmModel: LiveResource.MACHINE_POOLS,
            ProductionOrderOrmModel: LiveResource.PRODUCTION_ORDERS,
            UserOrmModel: LiveResource.USERS,
            PrinterOrmModel: LiveResource.PRINTERS,
            CalculationOrmModel: LiveResource.CALCULATIONS,
            ChecklistOrmModel: LiveResource.CHECKLISTS,
            SequenceOrmModel: LiveResource.SEQUENCES,
            MeetingOrmModel: LiveResource.MEETINGS,
        }
    )
    register_live_topics(
        {
            OrderOrmModel: (LiveTopic(LiveResource.ORDERS, "id"),),
            OrderItemOrmModel: (
                LiveTopic(LiveResource.ORDERS, "order_id", child=True),
                # None, a no-op, for order items without a lot position.
                LiveTopic(LiveResource.PRODUCTION_LOTS, "lot_position.lot_id", child=True),
            ),
            BoughtItemDemandItemOrmModel: (LiveTopic(LiveResource.BOUGHT_ITEM_DEMANDS, "id"),),
            BoughtItemAllocationOrmModel: (
                LiveTopic(LiveResource.BOUGHT_ITEM_DEMANDS, "demand_item_id", child=True),
            ),
            BoughtItemFileOrmModel: (
                LiveTopic(LiveResource.BOUGHT_ITEMS, "bought_item_id", child=True),
            ),
            # A picture stored in the background, such as the Data Portal picture or
            # a CAD rendering from PDM, reaches the thumbnails and the pictures of an
            # open page this way. Only one of the three foreign keys is set; the
            # other two resolve to None, a no-op.
            ItemPictureOrmModel: (
                LiveTopic(LiveResource.MADE_ITEMS, "made_item_id", child=True),
                LiveTopic(LiveResource.BOUGHT_ITEMS, "bought_item_id", child=True),
                LiveTopic(LiveResource.SOURCE_ITEMS, "source_item_id", child=True),
            ),
            MadeItemDemandItemOrmModel: (LiveTopic(LiveResource.MADE_ITEM_DEMANDS, "id"),),
            MadeItemAllocationOrmModel: (
                LiveTopic(LiveResource.MADE_ITEM_DEMANDS, "demand_item_id", child=True),
            ),
            SourceItemDemandItemOrmModel: (
                LiveTopic(LiveResource.SOURCE_ITEM_DEMANDS, "id"),
                # The demand status is also shown in the lots table.
                LiveTopic(LiveResource.PRODUCTION_LOTS, "lot_id", child=True),
            ),
            SourceItemAllocationOrmModel: (
                LiveTopic(LiveResource.SOURCE_ITEM_DEMANDS, "demand_item_id", child=True),
            ),
            # A quote request page and the "in quotation" markers of the demand
            # and lot tables follow the request through these; an offer is written
            # together with its request row, which signals it.
            QuoteRequestOrmModel: (LiveTopic(LiveResource.QUOTE_REQUESTS, "id"),),
            QuoteRequestLineOrmModel: (
                LiveTopic(LiveResource.QUOTE_REQUESTS, "quote_request_id", child=True),
            ),
            QuoteRequestLineDemandOrmModel: (
                LiveTopic(LiveResource.BOUGHT_ITEM_DEMANDS, "bought_demand_item_id", child=True),
                LiveTopic(LiveResource.SOURCE_ITEM_DEMANDS, "source_demand_item_id", child=True),
            ),
            QuoteRequestSupplierOrmModel: (
                LiveTopic(LiveResource.QUOTE_REQUESTS, "quote_request_id", child=True),
            ),
            ProductionLotOrmModel: (LiveTopic(LiveResource.PRODUCTION_LOTS, "id"),),
            LotPositionOrmModel: (LiveTopic(LiveResource.PRODUCTION_LOTS, "lot_id", child=True),),
            LotStepOrmModel: (LiveTopic(LiveResource.PRODUCTION_LOTS, "lot_id", child=True),),
            ProductionOrderOrmModel: (
                LiveTopic(LiveResource.PRODUCTION_ORDERS, "id"),
                # Order dates are also shown in the lots table.
                LiveTopic(LiveResource.PRODUCTION_LOTS, "lot_position.lot_id", child=True),
            ),
            ProductionMachineOrmModel: (LiveTopic(LiveResource.PRODUCTION_MACHINES, "id"),),
            MachinePoolOrmModel: (LiveTopic(LiveResource.MACHINE_POOLS, "id"),),
            PrinterOrmModel: (LiveTopic(LiveResource.PRINTERS, "id"),),
            AdminBannerSettingsOrmModel: (LiveTopic(LiveResource.ANNOUNCEMENTS, "id"),),
            AcknowledgementOrmModel: (LiveTopic(LiveResource.ANNOUNCEMENTS, "id"),),
            AcknowledgementRecipientOrmModel: (
                LiveTopic(LiveResource.ANNOUNCEMENTS, "acknowledgement_id", child=True),
            ),
            # A document page follows its edit lock and release through these.
            CalculationOrmModel: (LiveTopic(LiveResource.CALCULATIONS, "id"),),
            ChecklistOrmModel: (LiveTopic(LiveResource.CHECKLISTS, "id"),),
            SequenceOrmModel: (LiveTopic(LiveResource.SEQUENCES, "id"),),
            # The Devices tab of a product follows its devices through these.
            ProductDeviceOrmModel: (
                LiveTopic(LiveResource.PRODUCT_DEVICES, "product_id", child=True),
            ),
            ProductDeviceComponentOrmModel: (
                LiveTopic(LiveResource.PRODUCT_DEVICES, "product_id", child=True),
            ),
            # The terminals tab follows its rows, and a display follows its own row
            # (approval, screen assignment, reload and identify requests) and the
            # row of the screen it shows.
            TerminalOrmModel: (LiveTopic(LiveResource.TERMINALS, "id"),),
            InfoscreenOrmModel: (LiveTopic(LiveResource.INFOSCREENS, "id"),),
            # The default display schedule reaches the infoscreens page and every
            # display showing a screen.
            InfoscreenDisplayDefaultOrmModel: (LiveTopic(LiveResource.INFOSCREEN_DEFAULTS, "id"),),
            # Sending or ending a message to terminals reaches the terminals page
            # and every approved display.
            TerminalBroadcastOrmModel: (LiveTopic(LiveResource.TERMINAL_BROADCASTS, "id"),),
            # The contacts tab and the contact sections of the customer and
            # supplier dialogs follow the contacts, and the contact sections
            # of a product and a project follow their links.
            ContactOrmModel: (LiveTopic(LiveResource.CONTACTS, "id"),),
            ProductContactOrmModel: (
                LiveTopic(LiveResource.PRODUCT_CONTACTS, "product_id", child=True),
            ),
            ProjectContactOrmModel: (
                LiveTopic(LiveResource.PROJECT_CONTACTS, "project_id", child=True),
            ),
            # The meeting page and the meeting lists follow a meeting and
            # everything on its page through the meeting's id.
            MeetingOrmModel: (LiveTopic(LiveResource.MEETINGS, "id"),),
            MeetingAttendeeOrmModel: (LiveTopic(LiveResource.MEETINGS, "meeting_id", child=True),),
            MeetingTagOrmModel: (LiveTopic(LiveResource.MEETINGS, "meeting_id", child=True),),
            MeetingCardOrmModel: (LiveTopic(LiveResource.MEETINGS, "meeting_id", child=True),),
            MeetingDecisionOrmModel: (LiveTopic(LiveResource.MEETINGS, "meeting_id", child=True),),
            MeetingTodoOrmModel: (LiveTopic(LiveResource.MEETINGS, "meeting_id", child=True),),
            MeetingFileOrmModel: (LiveTopic(LiveResource.MEETINGS, "meeting_id", child=True),),
        }
    )
    register_notification_rules(DEMAND_NOTIFICATION_RULES)
    register_notification_rules(ORDER_NOTIFICATION_RULES)
    register_notification_rules(LOT_NOTIFICATION_RULES)
    register_notification_rules(PROJECT_NOTIFICATION_RULES)
    register_notification_rules(MEETING_NOTIFICATION_RULES)
    register_notification_rules(PRODUCT_NOTIFICATION_RULES)
    register_notification_rules(DOCUMENT_NOTIFICATION_RULES)
    bind_request_dependencies()
