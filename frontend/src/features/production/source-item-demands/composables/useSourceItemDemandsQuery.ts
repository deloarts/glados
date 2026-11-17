import { storeToRefs } from 'pinia'

import { buildCommonDemandFilterParams } from '@/shared/components/demands/demandFilterParams'

import { useSourceItemDemandsFiltersStore } from '../stores/sourceItemDemandsFiltersStore'

/**
 * The source item demands table's filters as list query params. The table
 * pages and refetches live rows with `filterParams`, and the export reads
 * the list with `listParams`, which adds the sort, so the file holds exactly
 * the rows the table filters to, in the same order.
 */
export function useSourceItemDemandsQuery() {
  const {
    search,
    idFilter,
    statusFilter,
    creatorFilter,
    projectId,
    itemDimension,
    itemMaterial,
    itemType,
    lotIds,
    orderIds,
    desiredFrom,
    desiredTo,
    showFulfilled,
    showCanceled,
    notFullyAllocatedOnly,
    bucketIds,
    includeUnbucketed,
    sortBy,
    sortDir,
  } = storeToRefs(useSourceItemDemandsFiltersStore())

  function filterParams() {
    return {
      ...buildCommonDemandFilterParams({
        idFilter,
        projectId,
        creatorFilter,
        showFulfilled,
        showCanceled,
        desiredFrom,
        desiredTo,
        notFullyAllocatedOnly,
        bucketIds,
        includeUnbucketed,
      }),
      ...(search.value.trim() ? { search: search.value.trim() } : {}),
      ...(statusFilter.value ? { status: statusFilter.value } : {}),
      ...(itemDimension.value ? { item_dimension: itemDimension.value } : {}),
      ...(itemMaterial.value ? { item_material: itemMaterial.value } : {}),
      ...(itemType.value ? { item_type: itemType.value } : {}),
      ...(lotIds.value.length > 0 ? { lot_id: lotIds.value } : {}),
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
