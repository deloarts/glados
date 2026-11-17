// Public barrel of the made-items feature. Other features import through
// here (enforced by eslint). Export only what other features consume.

export { getMadeItemChangelog } from './api/getMadeItemChangelog'
export { getMadeItemDemands } from './api/madeItemDemandsApi'
export { getMadeItemFileBlob } from './api/madeItemFilesApi'
export { getMadeItemRevisions } from './api/getMadeItemRevisions'
export { getMadeItems } from './api/getMadeItems'
export { useMadeItemDetail } from './composables/useMadeItemDetail'
export { madeItemLotDialogsKey } from './composables/useMadeItemLotDialogs'
export type { MadeItemLotDialogs } from './composables/useMadeItemLotDialogs'
export { useMadeItemFilesStore } from './stores/madeItemFilesStore'
export { useMadeItemPicturesStore } from './stores/madeItemPicturesStore'
export { useMadeItemsDemandsStore } from './stores/madeItemsDemandsStore'
export { formatMadeItemNumber, useMadeItemLabel } from './utils/madeItemLabel'

export type { MadeItemChangelogEntry } from './types/madeItemsChangelogResponse'
export type { MadeItemDemandResponse } from './types/madeItemsDemandsResponse'
export type { MadeItemFile, MadeItemResponse, MadeItemRevisionsResponse } from './types/madeItemsResponse'
export type { MaterialSource, MaterialSourceFieldLocks } from './types/materialSource'

export { default as MadeItemDemandCreateForm } from './components/MadeItemDemandCreateForm.vue'
export { default as MadeItemDetailDialog } from './components/MadeItemDetailDialog.vue'
export { default as MadeItemDetailFields } from './components/MadeItemDetailFields.vue'
export { default as MadeItemFilesCell } from './components/MadeItemFilesCell.vue'
export { default as MadeItemFilesSection } from './components/MadeItemFilesSection.vue'
export { default as MadeItemLinkedSourceCard } from './components/MadeItemLinkedSourceCard.vue'
export { default as MadeItemPicturesSection } from './components/MadeItemPicturesSection.vue'
export { default as MadeItemProcessEditor } from './components/MadeItemProcessEditor.vue'
export { default as MadeItemProcessGrouping } from './components/MadeItemProcessGrouping.vue'
export { default as MadeItemSelect } from './components/MadeItemSelect.vue'
export { default as MadeItemThumbnailCell } from './components/MadeItemThumbnailCell.vue'
export { default as MaterialSourceSelect } from './components/MaterialSourceSelect.vue'

// The demand API, its types and the item helpers the demand screens in
// Planning and fulfillment use.
export {
  getMadeItemDemandSummaryBatch,
  fulfillMadeItemDemandFromStock,
  getMadeItemAllocationsForDemand,
  updateMadeItemStockAllocation,
  deleteMadeItemStockAllocation,
  commitBatchMadeItemDemands,
  validateBatchMadeItemDemands,
} from './api/madeItemDemandsApi'
export { useMadeItemsStore } from './stores/madeItemsStore'
export { groupMethodLabel, processGroups, processRoutingLabel } from './utils/madeItemProcessGroups'
export type {
  MadeItemAllocationResponse,
  MadeItemDemandSummaryResponse,
  MadeItemFulfillFromStockResponse,
} from './types/madeItemsAllocationsResponse'
export type {
  CommitBatchMadeItemDemandsRequest,
  CommitBatchMadeItemDemandsResponse,
  MadeItemBatchDemandRowInput,
  MadeItemBatchDivergenceField,
  MadeItemRowValidationResult,
  ValidateBatchMadeItemDemandsRequest,
  ValidateBatchMadeItemDemandsResponse,
} from './types/madeItemsDemandsBatchTypes'
export type { MadeItemDemandSortBy } from './types/madeItemsDemandsRequest'
export type {
  CancelImpactLot,
  MadeItemDemandCancelImpact,
  MadeItemDemandStatus,
} from './types/madeItemsDemandsResponse'
