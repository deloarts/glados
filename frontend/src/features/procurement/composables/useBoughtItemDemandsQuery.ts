import { storeToRefs } from 'pinia'

import { buildCommonDemandFilterParams } from '@/shared/components/demands/demandFilterParams'

import { useBoughtItemsDemandsFiltersStore } from '../stores/boughtItemsDemandsFiltersStore'

/**
 * The bought item demands table's filters as list query params. The table
 * pages and refetches live rows with `filterParams`, and the export reads
 * the list with `listParams`, which adds the sort, so the file holds exactly
 * the rows the table filters to, in the same order.
 */
export function useBoughtItemDemandsQuery() {
  const {
    search,
    projectId,
    itemArticleName,
    itemManufacturerId,
    statusFilter,
    highPriorityFilter,
    creatorFilter,
    showFulfilled,
    showCanceled,
    desiredFrom,
    desiredTo,
    createdFrom,
    createdTo,
    notFullyAllocatedOnly,
    bucketIds,
    includeUnbucketed,
    idFilter,
    orderIds,
    sortBy,
    sortDir,
  } = storeToRefs(useBoughtItemsDemandsFiltersStore())

  function filterParams() {
    return {
      ...buildCommonDemandFilterParams({
        search,
        idFilter,
        projectId,
        itemArticleName,
        highPriorityFilter,
        creatorFilter,
        showFulfilled,
        showCanceled,
        desiredFrom,
        desiredTo,
        createdFrom,
        createdTo,
        notFullyAllocatedOnly,
        bucketIds,
        includeUnbucketed,
      }),
      ...(itemManufacturerId.value ? { item_manufacturer_id: itemManufacturerId.value } : {}),
      ...(statusFilter.value ? { status: statusFilter.value } : {}),
      ...(orderIds.value.length > 0 ? { order_id: orderIds.value } : {}),
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
