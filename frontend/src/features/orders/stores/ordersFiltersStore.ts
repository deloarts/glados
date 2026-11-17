import { ref } from 'vue'

import { createFiltersStore } from '@/shared/stores/createFiltersStore'
import type { FiltersStoreBase } from '@/shared/stores/createFiltersStore'

import type { OrderStatus } from '../types/ordersResponse'
import type { OrderSortBy } from '../types/ordersRequest'

export type OrderGroupBy = 'status' | 'supplier' | null

/**
 * `missing` keeps only orders without an invoice file, `present` only
 * those with at least one; null leaves the file table out of the query.
 */
export type OrderInvoiceFilter = 'missing' | 'present' | null

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type OrdersFilterFields = {
  search: string
  orderNumberFilter: string
  noteFilter: string
  storagePlaceFilter: string
  statusFilter: OrderStatus[]
  supplierFilter: number | null
  creatorFilter: number | null
  orderedFrom: Date | null
  orderedTo: Date | null
  expectedDeliveryFrom: Date | null
  expectedDeliveryTo: Date | null
  deliveredFrom: Date | null
  deliveredTo: Date | null
  createdFrom: Date | null
  createdTo: Date | null
  hideDelivered: boolean
  hideCanceled: boolean
  invoiceFilter: OrderInvoiceFilter
}

function extend(base: FiltersStoreBase<OrdersFilterFields, OrderSortBy, true>) {
  const showActions = ref(false)
  const showOrderFiles = ref(true)
  const groupBy = ref<OrderGroupBy>(null)

  function setGroupBy(value: Exclude<OrderGroupBy, null>): void {
    groupBy.value = groupBy.value === value ? null : value
  }

  function clearGroupBy(): void {
    groupBy.value = null
  }

  function toggleShowActions(): void {
    showActions.value = !showActions.value
  }

  function toggleShowOrderFiles(): void {
    showOrderFiles.value = !showOrderFiles.value
  }

  function toggleHideDelivered(): void {
    base.hideDelivered.value = !base.hideDelivered.value
  }

  function toggleHideCanceled(): void {
    base.hideCanceled.value = !base.hideCanceled.value
  }

  function toggleMissingInvoice(): void {
    base.invoiceFilter.value = base.invoiceFilter.value === 'missing' ? null : 'missing'
  }

  return {
    state: {
      showActions,
      showOrderFiles,
      groupBy,
      setGroupBy,
      clearGroupBy,
      toggleShowActions,
      toggleShowOrderFiles,
      toggleHideDelivered,
      toggleHideCanceled,
      toggleMissingInvoice,
    },
    onClear: () => {
      groupBy.value = null
    },
  }
}

export const useOrdersFiltersStore = createFiltersStore<
  OrdersFilterFields,
  OrderSortBy,
  true,
  ReturnType<typeof extend>['state']
>('ordersFilters', {
  defaults: {
    search: '',
    orderNumberFilter: '',
    noteFilter: '',
    storagePlaceFilter: '',
    statusFilter: [],
    supplierFilter: null,
    creatorFilter: null,
    orderedFrom: null,
    orderedTo: null,
    expectedDeliveryFrom: null,
    expectedDeliveryTo: null,
    deliveredFrom: null,
    deliveredTo: null,
    createdFrom: null,
    createdTo: null,
    hideDelivered: false,
    hideCanceled: false,
    invoiceFilter: null,
  },
  // Arrays need a length check, since the default equality compares by
  // reference.
  isActive: (fields) =>
    fields.search !== '' ||
    fields.orderNumberFilter !== '' ||
    fields.noteFilter !== '' ||
    fields.storagePlaceFilter !== '' ||
    fields.statusFilter.length > 0 ||
    fields.supplierFilter !== null ||
    fields.creatorFilter !== null ||
    fields.orderedFrom !== null ||
    fields.orderedTo !== null ||
    fields.expectedDeliveryFrom !== null ||
    fields.expectedDeliveryTo !== null ||
    fields.deliveredFrom !== null ||
    fields.deliveredTo !== null ||
    fields.createdFrom !== null ||
    fields.createdTo !== null ||
    fields.hideDelivered ||
    fields.hideCanceled ||
    fields.invoiceFilter !== null,
  sortable: true,
  extend,
})
