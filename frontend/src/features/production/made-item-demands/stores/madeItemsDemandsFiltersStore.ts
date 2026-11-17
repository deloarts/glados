import { createDemandFiltersStore } from '@/shared/stores/createDemandFiltersStore'

import { useMadeItemsProcurementStore } from './madeItemsProcurementStore'
import type { MadeItemDemandStatus, MadeItemDemandSortBy } from '@/features/made-items'


export type MadeItemDemandGroupBy = 'status' | 'project' | 'bucket' | null

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type MadeItemsDemandsFilterFields = {
  search: string
  // Exact id match from the id column's number input, sent as `ids: [n]`.
  idFilter: number | null
  projectId: number | null
  itemArticleName: string
  statuses: MadeItemDemandStatus[]
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
  // Any-of, encoded as fabrication:<id> or inspection:<id>.
  stepMethods: string[]
  // Lots picked in the lots column's lookup, any-of.
  lotIds: number[]
}

const PANELS = { lots: 'showManageLotsPanel', stock: 'showManageStockPanel' } as const

export const useMadeItemsDemandsFiltersStore = createDemandFiltersStore<
  MadeItemsDemandsFilterFields,
  MadeItemDemandSortBy,
  Exclude<MadeItemDemandGroupBy, null>,
  typeof PANELS,
  { toggleManageLotsPanel: () => void }
>('madeItemsDemandsFilters', {
  // A factory, so clearAll() never hands back a shared array.
  defaults: () => ({
    search: '',
    idFilter: null,
    projectId: null,
    itemArticleName: '',
    statuses: [],
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
    stepMethods: [],
    lotIds: [],
  }),
  // Arrays need a length check, since the default equality compares by
  // reference.
  isActive: (fields) =>
    fields.search !== '' ||
    fields.idFilter !== null ||
    fields.projectId !== null ||
    fields.itemArticleName !== '' ||
    fields.statuses.length > 0 ||
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
    fields.stepMethods.length > 0 ||
    fields.lotIds.length > 0,
  panels: PANELS,
  useSelectionStore: useMadeItemsProcurementStore,
  // An alias of togglePanel('lots') that specs drive the lots panel through.
  extend: (state) => ({
    toggleManageLotsPanel: () => state.togglePanel('lots'),
  }),
})
