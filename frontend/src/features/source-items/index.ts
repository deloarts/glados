// Public barrel of the source-items feature. Other features import through
// here (enforced by eslint). Export only what other features consume.

export { getSourceItemChangelog } from './api/getSourceItemChangelog'
export { getSourceItemDemand } from './api/getSourceItemDemand'
export { getSourceItemDemands } from './api/sourceItemDemandsApi'
export { getSourceItemFileBlob } from './api/sourceItemFilesApi'
export { sourceItemsApi } from './api/sourceItemsApi'
export { useSourceItemDetail } from './composables/useSourceItemDetail'
export { useSourceItemDemandsStore } from './stores/sourceItemDemandsStore'
export { useSourceItemFilesStore } from './stores/sourceItemFilesStore'
export { useSourceItemPicturesStore } from './stores/sourceItemPicturesStore'
export {
  itemKind,
  itemLabel,
  itemManufacturer,
  itemOrderCode1,
  itemOrderCode2,
  itemSublabel,
} from './utils/sourceItemDemandLabels'
export { detectDimensionShape, sourceItemPlaceholder } from './utils/sourceItemPlaceholder'

export type { SourceItemDemandResponse, SourceItemDemandStatus } from './types/sourceItemDemandsResponse'
export type {
  SourceItemAllocationResponse,
  SourceItemDemandSummaryResponse,
} from './types/sourceItemsAllocationsResponse'
export type { SourceItemFile, SourceItemFileCategory } from './types/sourceItemsResponse'
export type { SourceItemChangelogEntry } from './types/sourceItemsChangelogResponse'
export type { SourceItemResponse } from './types/sourceItemsResponse'

export { default as SourceItemDetailDialog } from './components/SourceItemDetailDialog.vue'
export { default as SourceItemDetailFields } from './components/SourceItemDetailFields.vue'
export { default as SourceItemFilesSection } from './components/SourceItemFilesSection.vue'
export { default as SourceItemInlineCreateForm } from './components/SourceItemInlineCreateForm.vue'
export { default as SourceItemPicturesSection } from './components/SourceItemPicturesSection.vue'
export { default as SourceItemSelect } from './components/SourceItemSelect.vue'
export { default as SourceItemThumbnailCell } from './components/SourceItemThumbnailCell.vue'

// The demand API, its types and the item helpers the demand screens in
// Planning and fulfillment use.
export {
  getSourceItemDemandSummaryBatch,
  autoAllocateSourceItemDemand,
  fulfillSourceItemDemandFromStock,
  getAllocationsForSourceItemDemand,
  createSourceItemAllocation,
  updateSourceItemAllocation,
  deleteSourceItemAllocation,
  updateSourceItemStockAllocation,
  deleteSourceItemStockAllocation,
} from './api/sourceItemDemandsApi'
export type { SourceItemAllocationCreateRequest } from './api/sourceItemDemandsApi'
export type { SourceItemDemandSortBy } from './types/sourceItemDemandsRequest'
export type {
  AutoAllocateSourceItemDemandResponse,
  FulfillSourceItemDemandFromStockResponse,
} from './types/sourceItemsAllocationsResponse'
