import { createDemandFiltersStore } from '@/shared/stores/createDemandFiltersStore'

import { useBoughtItemsProcurementStore } from './boughtItemsProcurementStore'
import type { BoughtItemDemandStatus, DemandItemSortBy } from '@/features/bought-items'


export type BoughtItemDemandGroupBy = 'status' | 'project' | 'manufacturer' | 'bucket' | null

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type BoughtItemsDemandsFilterFields = {
  search: string
  // Exact id match from the id column's number input, sent as `ids: [n]`.
  idFilter: number | null
  projectId: number | null
  itemArticleName: string
  itemManufacturerId: number | null
  statusFilter: BoughtItemDemandStatus | null
  highPriorityFilter: boolean | null
  creatorFilter: number | null
  showFulfilled: boolean
  showCanceled: boolean
  desiredFrom: Date | null
  desiredTo: Date | null
  createdFrom: Date | null
  createdTo: Date | null
  // Set when a Manage panel opens, since those panels only act on demands with
  // quantity left. A field of its own so Clear can widen the list while the
  // panel stays open.
  notFullyAllocatedOnly: boolean
  // Display state only. Empty means no bucket filter.
  bucketIds: number[]
  includeUnbucketed: boolean
  // Any-of.
  orderIds: number[]
}

const PANELS = {
  orders: 'showManageOrderPanel',
  stock: 'showManageStockPanel',
  quotes: 'showManageQuotePanel',
} as const

export const useBoughtItemsDemandsFiltersStore = createDemandFiltersStore<
  BoughtItemsDemandsFilterFields,
  DemandItemSortBy,
  Exclude<BoughtItemDemandGroupBy, null>,
  typeof PANELS
>('boughtItemsDemandsFilters', {
  // A factory, so clearAll() never hands back a shared array.
  defaults: () => ({
    search: '',
    idFilter: null,
    projectId: null,
    itemArticleName: '',
    itemManufacturerId: null,
    statusFilter: null,
    highPriorityFilter: null,
    creatorFilter: null,
    showFulfilled: false,
    showCanceled: false,
    desiredFrom: null,
    desiredTo: null,
    createdFrom: null,
    createdTo: null,
    notFullyAllocatedOnly: false,
    bucketIds: [],
    includeUnbucketed: false,
    orderIds: [],
  }),
  // Arrays need a length check, since the default equality compares by
  // reference.
  isActive: (fields) =>
    fields.search !== '' ||
    fields.idFilter !== null ||
    fields.projectId !== null ||
    fields.itemArticleName !== '' ||
    fields.itemManufacturerId !== null ||
    fields.statusFilter !== null ||
    fields.highPriorityFilter !== null ||
    fields.creatorFilter !== null ||
    fields.showFulfilled ||
    fields.showCanceled ||
    fields.desiredFrom !== null ||
    fields.desiredTo !== null ||
    fields.createdFrom !== null ||
    fields.createdTo !== null ||
    fields.notFullyAllocatedOnly ||
    fields.bucketIds.length > 0 ||
    fields.includeUnbucketed ||
    fields.orderIds.length > 0,
  panels: PANELS,
  useSelectionStore: useBoughtItemsProcurementStore,
})
