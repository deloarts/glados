import { createFiltersStore } from '@/shared/stores/createFiltersStore'

import type { ProductionOrderStatus } from '@/features/production'

export type QaSortBy = 'planned' | 'part' | 'lot' | 'quantity'
export type QaSortDir = 'asc' | 'desc'

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type QaFilterFields = {
  search: string
  showCompleted: boolean
  showCanceled: boolean
  showFuture: boolean
  // Column filters of the task table, all applied server side. A status
  // pick replaces the completed and canceled toggles on the server, the
  // future toggle still applies on top of it.
  statuses: ProductionOrderStatus[]
  inspectionMethodIds: number[]
  lotNumber: string
  projectNumber: string
  itemText: string
  quantityMin: number | null
  quantityMax: number | null
  plannedStartFrom: Date | null
  plannedStartTo: Date | null
  finishedFrom: Date | null
  finishedTo: Date | null
  finishedByIds: number[]
}

// Each toggle reveals more than the default worklist, so all default to
// false and count as active filters when on.
export const useQaFiltersStore = createFiltersStore<QaFilterFields, QaSortBy, true>('qaFilters', {
  // A factory, so every clearAll() hands out fresh arrays rather than the
  // same default array a MultiSelect may have been bound to.
  defaults: () => ({
    search: '',
    showCompleted: false,
    showCanceled: false,
    showFuture: false,
    statuses: [],
    inspectionMethodIds: [],
    lotNumber: '',
    projectNumber: '',
    itemText: '',
    quantityMin: null,
    quantityMax: null,
    plannedStartFrom: null,
    plannedStartTo: null,
    finishedFrom: null,
    finishedTo: null,
    finishedByIds: [],
  }),
  // Arrays need a length check, since the default equality compares by
  // reference.
  isActive: (fields) =>
    fields.search !== '' ||
    fields.showCompleted ||
    fields.showCanceled ||
    fields.showFuture ||
    fields.statuses.length > 0 ||
    fields.inspectionMethodIds.length > 0 ||
    fields.lotNumber !== '' ||
    fields.projectNumber !== '' ||
    fields.itemText !== '' ||
    fields.quantityMin !== null ||
    fields.quantityMax !== null ||
    fields.plannedStartFrom !== null ||
    fields.plannedStartTo !== null ||
    fields.finishedFrom !== null ||
    fields.finishedTo !== null ||
    fields.finishedByIds.length > 0,
  sortable: true,
})
