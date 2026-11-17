import { createDemandFiltersStore } from '@/shared/stores/createDemandFiltersStore'

import { useSourceItemDemandsSelectionStore } from './sourceItemDemandsSelectionStore'
import type { SourceItemDemandStatus, SourceItemDemandSortBy } from '@/features/source-items'


export type SourceItemDemandGroupBy = 'status' | 'project' | 'bucket' | null

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type SourceItemDemandsFilterFields = {
  // The views bar's search box, matched server side against project, lot,
  // material, bought item and note.
  search: string
  // Exact id match, sent as a one-element `ids` list.
  idFilter: number | null
  statusFilter: SourceItemDemandStatus | null
  creatorFilter: number | null
  projectId: number | null
  // The three source item inputs stacked in the item column, ANDed server
  // side. They only match the source item side of a demand.
  itemDimension: string
  itemMaterial: string
  itemType: string
  // Any-of picks from the lot and order lookups. Empty means no predicate.
  lotIds: number[]
  orderIds: number[]
  desiredFrom: Date | null
  desiredTo: Date | null
  showFulfilled: boolean
  showCanceled: boolean
  // Set when a Manage panel opens, since those panels only act on demands with
  // quantity left. A field of its own so Clear can widen the list while the
  // panel stays open.
  notFullyAllocatedOnly: boolean
  // Display state only. Empty means no bucket filter.
  bucketIds: number[]
  includeUnbucketed: boolean
}

const PANELS = {
  orders: 'showManageOrderPanel',
  stock: 'showManageStockPanel',
  quotes: 'showManageQuotePanel',
} as const

export const useSourceItemDemandsFiltersStore = createDemandFiltersStore<
  SourceItemDemandsFilterFields,
  SourceItemDemandSortBy,
  Exclude<SourceItemDemandGroupBy, null>,
  typeof PANELS
>('sourceItemDemandsFilters', {
  // A factory, so clearAll() never hands back a shared array.
  defaults: () => ({
    search: '',
    idFilter: null,
    statusFilter: null,
    creatorFilter: null,
    projectId: null,
    itemDimension: '',
    itemMaterial: '',
    itemType: '',
    lotIds: [],
    orderIds: [],
    desiredFrom: null,
    desiredTo: null,
    showFulfilled: false,
    showCanceled: false,
    notFullyAllocatedOnly: false,
    bucketIds: [],
    includeUnbucketed: false,
  }),
  // Arrays need a length check, since the default equality compares by
  // reference.
  isActive: (fields) =>
    fields.search !== '' ||
    fields.idFilter !== null ||
    fields.statusFilter !== null ||
    fields.creatorFilter !== null ||
    fields.projectId !== null ||
    fields.itemDimension !== '' ||
    fields.itemMaterial !== '' ||
    fields.itemType !== '' ||
    fields.lotIds.length > 0 ||
    fields.orderIds.length > 0 ||
    fields.desiredFrom !== null ||
    fields.desiredTo !== null ||
    fields.showFulfilled ||
    fields.showCanceled ||
    fields.notFullyAllocatedOnly ||
    fields.bucketIds.length > 0 ||
    fields.includeUnbucketed,
  panels: PANELS,
  useSelectionStore: useSourceItemDemandsSelectionStore,
})
