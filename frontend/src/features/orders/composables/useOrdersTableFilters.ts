import { computed, watch, type Ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import { useServerTable } from '@/core/composables/useServerTable'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useLiveRows } from '@/core/realtime/useLiveRows'
import { LiveResource } from '@/core/realtime/resources'
import { useUsersStore } from '@/core/stores/usersStore'

import { useOrdersStore } from '../stores/ordersStore'
import { useOrdersFiltersStore } from '../stores/ordersFiltersStore'
import { ORDER_STATUSES, useOrdersQuery } from './useOrdersQuery'
import { getOrders } from '../api/getOrders'

import type { OrderResponse, OrderStatus } from '../types/ordersResponse'


const SETTABLE_EXPECTED_DELIVERY_STATUSES: OrderStatus[] = [
  'draft',
  'requested',
  'partially_ordered',
  'ordered',
  'partially_delivered',
]

// Filtering, sorting, grouping and paging of the orders table. expandedRows
// comes in because a search auto-expands its results.
export function useOrdersTableFilters(expandedRows: Ref<Record<string, boolean>>) {
  const { t } = useI18n()
  const ordersStore = useOrdersStore()
  const filtersStore = useOrdersFiltersStore()
  const usersStore = useUsersStore()

  const {
    search,
    orderNumberFilter,
    noteFilter,
    storagePlaceFilter,
    statusFilter,
    supplierFilter,
    creatorFilter,
    orderedFrom,
    orderedTo,
    expectedDeliveryFrom,
    expectedDeliveryTo,
    deliveredFrom,
    deliveredTo,
    createdFrom,
    createdTo,
    clearTrigger,
    hideDelivered,
    hideCanceled,
    invoiceFilter,
    sortBy,
    sortDir,
    groupBy,
  } = storeToRefs(filtersStore)

  const statusOptions = computed(() =>
    ORDER_STATUSES.map((s) => ({ label: t(`orders.status.${s}`), value: s })),
  )

  // Filters without paging or sort, shared with the live ids refetch and the export.
  const { filterParams: buildFilterParams, listParams } = useOrdersQuery()

  const groupedItems = computed(() => {
    const items = ordersStore.items
    if (!groupBy.value) return items

    if (groupBy.value === 'status') {
      return groupRowsByLabel(items, '_statusGroup', (item) => t(`orders.status.${item.status}`))
    }

    return groupRowsByLabel(items, '_supplierGroup', (item) => item.supplier_name)
  })

  const groupRowsBy = computed(() => {
    if (!groupBy.value) return undefined
    return groupBy.value === 'status' ? '_statusGroup' : '_supplierGroup'
  })

  const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable(
    {
      fetchParams: ({ first, rows }) => ({
        skip: first,
        limit: rows,
        ...listParams(),
      }),
      fetch: async (params) => {
        await ordersStore.refresh(params)
        if (search.value) {
          expandedRows.value = Object.fromEntries(ordersStore.items.map((o) => [String(o.id), true]))
        }
        void usersStore.ensureLoaded()
      },
    },
  )

  const { items: liveItems, total: liveTotal } = storeToRefs(ordersStore)
  useLiveRows<OrderResponse>({
    resource: LiveResource.ORDERS,
    items: liveItems,
    total: liveTotal,
    fetchByIds: async (ids) => {
      const response = await getOrders({ ...buildFilterParams(), ids })
      return response.items
    },
    onFullRefresh: fetchItems,
  })

  watch(search, resetAndFetchDebounced)

  watch([orderNumberFilter, noteFilter, storagePlaceFilter], resetAndFetchDebounced)

  watch(
    [
      statusFilter,
      supplierFilter,
      creatorFilter,
      orderedFrom,
      orderedTo,
      expectedDeliveryFrom,
      expectedDeliveryTo,
      deliveredFrom,
      deliveredTo,
      createdFrom,
      createdTo,
      hideDelivered,
      hideCanceled,
      invoiceFilter,
    ],
    resetAndFetch,
  )

  watch(clearTrigger, resetAndFetch)

  watch([sortBy, sortDir], resetAndFetch)

  watch(
    () => ordersStore.refreshTrigger,
    () => fetchItems(),
  )

  // Each setter also resets paging and refetches, a server-table concern.
  const orderedDateRange = useDateRangeFilter(orderedFrom, orderedTo)
  const expectedDeliveryDateRange = useDateRangeFilter(expectedDeliveryFrom, expectedDeliveryTo)
  const deliveredDateRange = useDateRangeFilter(deliveredFrom, deliveredTo)
  const createdDateRange = useDateRangeFilter(createdFrom, createdTo)

  function setOrderedDateRange(value: Date | Array<Date | null> | null | undefined): void {
    orderedDateRange.value = value
    first.value = 0
    fetchItems()
  }

  function setExpectedDeliveryRange(value: Date | Array<Date | null> | null | undefined): void {
    expectedDeliveryDateRange.value = value
    first.value = 0
    fetchItems()
  }

  function setDeliveredDateRange(value: Date | Array<Date | null> | null | undefined): void {
    deliveredDateRange.value = value
    first.value = 0
    fetchItems()
  }

  function setCreatedDateRange(value: Date | Array<Date | null> | null | undefined): void {
    createdDateRange.value = value
    first.value = 0
    fetchItems()
  }

  function isExpectedDeliverySettable(order: OrderResponse): boolean {
    return SETTABLE_EXPECTED_DELIVERY_STATUSES.includes(order.status)
  }

  return {
    search,
    orderNumberFilter,
    noteFilter,
    storagePlaceFilter,
    statusFilter,
    supplierFilter,
    creatorFilter,
    groupBy,
    statusOptions,
    groupedItems,
    groupRowsBy,
    first,
    rows,
    fetchItems,
    onPage,
    orderedDateRange,
    expectedDeliveryDateRange,
    deliveredDateRange,
    createdDateRange,
    setOrderedDateRange,
    setExpectedDeliveryRange,
    setDeliveredDateRange,
    setCreatedDateRange,
    isExpectedDeliverySettable,
  }
}
