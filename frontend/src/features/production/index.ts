// Public barrel of the production feature. Other features import through
// here (enforced by eslint). Export only what other features consume.

export { getLot } from './api/getLot'
export { getLots } from './api/getLots'
export { getProductionOrderFileBlob } from './api/getProductionOrderFileBlob'
export { useProductionSchedule } from './composables/useProductionSchedule'
export { assignExternalPosition } from './lots/api/assignExternalPosition'
export { autoAssignLots } from './lots/api/autoAssignLots'
export { getProductionOrder } from './lots/api/getProductionOrder'
export { previewAutoAssignLots } from './lots/api/previewAutoAssignLots'
export { unassignExternalPosition } from './lots/api/unassignExternalPosition'
export { useLotNumberCache } from './lots/composables/useLotNumberCache'
export { useProductionLotDetailStore } from './lots/stores/productionLotDetailStore'
export { useProductionLotsStore } from './stores/productionLotsStore'
export { useProductionOrderFilesStore } from './stores/productionOrderFilesStore'
export { useProductionQueueStore } from './stores/productionQueueStore'
export { LOT_PRIORITIES, lotStatusSeverity } from './utils/lotStatus'
export { productionOrderStatusSeverity } from './utils/productionOrderStatus'
export { computeProductionSchedule } from './utils/productionPlanningTasks'
export { inspectionReportSpec } from './lots/utils/inspectionReport'
export { getProductionWip } from './wip/api/getProductionWip'

export type {
  AutoAssignLotGroupResponse,
  LotPositionResponse,
  LotPriority,
  LotResponse,
  LotStatus,
  LotStepResponse,
  LotSummaryResponse,
} from './types/productionLotsResponse'
export type {
  ProductionOrderCompletionResponse,
  ProductionOrderPriority,
  ProductionOrderResponse,
  ProductionOrderStatus,
  ScheduleConflict,
  ScrapReason,
} from './types/productionOrdersResponse'
export type { ProjectedSpan } from './utils/productionPlanningTasks'
export type { WipLotResponse } from './wip/types/productionWipResponse'

export { default as LotCreateDialog } from './lots/components/LotCreateDialog.vue'
export { default as LotPositionAssignDialog } from './lots/components/LotPositionAssignDialog.vue'
export { default as LotPositionProvisionDialog } from './lots/components/LotPositionProvisionDialog.vue'
export { default as SourceItemDemandCreateDialog } from './lots/components/SourceItemDemandCreateDialog.vue'
export { default as ProductionOrderCompletionDialog } from './components/ProductionOrderCompletionDialog.vue'
export { default as ProductionOrderStartDialog } from './queue/components/ProductionOrderStartDialog.vue'
export { default as ManufacturingAssessmentDialog } from './queue/components/ManufacturingAssessmentDialog.vue'

// The demand details for the item pages, and the lot history the page
// hosting the made-item catalogue provides to it.
export { default as MadeItemDemandDetailDialog } from './made-item-demands/components/MadeItemDemandDetailDialog.vue'
export { default as SourceItemDemandDetailDialog } from './source-item-demands/components/SourceItemDemandDetailDialog.vue'
export { default as MadeItemHistoryDialog } from './lots/components/MadeItemHistoryDialog.vue'
