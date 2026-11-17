// Public barrel of the bought-items feature. Other features import through
// here (enforced by eslint). Export only what other features consume.

export { getBoughtItemChangelog } from './api/getBoughtItemChangelog'
export { getBoughtItemFileBlob } from './api/boughtItemFilesApi'
export { getBoughtItems } from './api/getBoughtItems'
export { getDemands } from './api/boughtItemDemandsApi'
export { useBoughtItemDetail } from './composables/useBoughtItemDetail'
export { boughtItemOrderDialogsKey } from './composables/useBoughtItemOrderDialogs'
export type { BoughtItemOrderDialogs } from './composables/useBoughtItemOrderDialogs'
export { useBoughtItemsDemandsStore } from './stores/boughtItemsDemandsStore'
export { useBoughtItemPicturesStore } from './stores/boughtItemPicturesStore'
export { useBoughtItemFilesStore } from './stores/boughtItemFilesStore'

export type { BoughtItemChangelogEntry } from './types/boughtItemsChangelogResponse'
export type { BoughtItemDemandResponse } from './types/boughtItemsDemandsResponse'
export type { BoughtItemResponse } from './types/boughtItemsResponse'

export { default as BoughtItemDemandCreateForm } from './components/BoughtItemDemandCreateForm.vue'
export { default as BoughtItemDetailDialog } from './components/BoughtItemDetailDialog.vue'
export { default as BoughtItemDetailFields } from './components/BoughtItemDetailFields.vue'
export { default as BoughtItemEdpLookupDialog } from './components/BoughtItemEdpLookupDialog.vue'
export { default as BoughtItemPicturesSection } from './components/BoughtItemPicturesSection.vue'
export { default as BoughtItemSelect } from './components/BoughtItemSelect.vue'
export { default as BoughtItemThumbnailCell } from './components/BoughtItemThumbnailCell.vue'

// The demand API, its types and the item helpers the demand screens in
// Planning and fulfillment use.
export {
  getDemandSummaryBatch,
  autoAllocateDemand,
  fulfillDemandFromStock,
  getAllocationsForDemand,
  createAllocation,
  updateAllocation,
  deleteAllocation,
  updateStockAllocation,
  deleteStockAllocation,
  commitBatchDemands,
  validateBatchDemands,
} from './api/boughtItemDemandsApi'
export type { AllocationCreateRequest } from './api/boughtItemDemandsApi'
export type {
  AllocationResponse,
  AutoAllocateResponse,
  DemandSummaryResponse,
  FulfillFromStockResponse,
} from './types/boughtItemsAllocationsResponse'
export type {
  BatchDemandRowInput,
  BatchDivergenceField,
  CommitBatchDemandsRequest,
  CommitBatchDemandsResponse,
  RowValidationResult,
  ValidateBatchDemandsRequest,
  ValidateBatchDemandsResponse,
} from './types/boughtItemsDemandsBatchTypes'
export type { DemandItemSortBy } from './types/boughtItemsDemandsRequest'
export type { BoughtItemDemandStatus } from './types/boughtItemsDemandsResponse'
