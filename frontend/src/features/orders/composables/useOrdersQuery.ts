import { storeToRefs } from 'pinia'

import { dateToParam } from '@/core/utils/dates'

import { useOrdersFiltersStore } from '../stores/ordersFiltersStore'

import type { OrderStatus } from '../types/ordersResponse'

export const ORDER_STATUSES: OrderStatus[] = [
  'draft',
  'requested',
  'partially_ordered',
  'ordered',
  'partially_delivered',
  'delivered',
  'canceled',
]

/**
 * The orders table's filters as list query params. The table pages and
 * refetches live rows with `filterParams`, and the export reads the list
 * with `listParams`, which adds the sort, so the file holds exactly the
 * orders the table filters to, in the same order.
 */
export function useOrdersQuery() {
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
    hideDelivered,
    hideCanceled,
    invoiceFilter,
    sortBy,
    sortDir,
  } = storeToRefs(useOrdersFiltersStore())

  function effectiveStatusFilter(): OrderStatus[] | undefined {
    if (statusFilter.value.length === 0 && !hideDelivered.value && !hideCanceled.value) {
      return undefined
    }
    let statuses = statusFilter.value.length > 0 ? statusFilter.value : ORDER_STATUSES
    if (hideDelivered.value) statuses = statuses.filter((s) => s !== 'delivered')
    if (hideCanceled.value) statuses = statuses.filter((s) => s !== 'canceled')
    return statuses
  }

  function filterParams() {
    const status = effectiveStatusFilter()
    return {
      ...(search.value ? { search: search.value } : {}),
      ...(orderNumberFilter.value ? { order_number: orderNumberFilter.value } : {}),
      ...(noteFilter.value ? { note: noteFilter.value } : {}),
      ...(storagePlaceFilter.value ? { storage_place: storagePlaceFilter.value } : {}),
      ...(status ? { status } : {}),
      ...(supplierFilter.value ? { supplier_id: supplierFilter.value } : {}),
      ...(creatorFilter.value ? { creator_id: creatorFilter.value } : {}),
      ...(invoiceFilter.value ? { has_invoice: invoiceFilter.value === 'present' } : {}),
      ...(orderedFrom.value ? { ordered_from: dateToParam(orderedFrom.value) ?? undefined } : {}),
      ...(orderedTo.value ? { ordered_to: dateToParam(orderedTo.value) ?? undefined } : {}),
      ...(expectedDeliveryFrom.value
        ? { expected_delivery_from: dateToParam(expectedDeliveryFrom.value) ?? undefined }
        : {}),
      ...(expectedDeliveryTo.value
        ? { expected_delivery_to: dateToParam(expectedDeliveryTo.value) ?? undefined }
        : {}),
      ...(deliveredFrom.value
        ? { delivered_from: dateToParam(deliveredFrom.value) ?? undefined }
        : {}),
      ...(deliveredTo.value ? { delivered_to: dateToParam(deliveredTo.value) ?? undefined } : {}),
      ...(createdFrom.value ? { created_from: dateToParam(createdFrom.value) ?? undefined } : {}),
      ...(createdTo.value ? { created_to: dateToParam(createdTo.value) ?? undefined } : {}),
    }
  }

  function listParams() {
    return {
      ...filterParams(),
      ...(sortBy.value ? { order_by: sortBy.value, order_dir: sortDir.value } : {}),
    }
  }

  return { filterParams, listParams }
}
