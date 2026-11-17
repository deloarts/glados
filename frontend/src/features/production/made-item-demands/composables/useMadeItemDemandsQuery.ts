import { storeToRefs } from 'pinia'

import { buildCommonDemandFilterParams } from '@/shared/components/demands/demandFilterParams'

import { useMadeItemsDemandsFiltersStore } from '../stores/madeItemsDemandsFiltersStore'
import { decodeStepMethods } from '../utils/stepMethodFilter'

/**
 * The made item demands table's filters as list query params. The table
 * pages and refetches live rows with `filterParams`, and the export reads
 * the list with `listParams`, which adds the sort, so the file holds exactly
 * the rows the table filters to, in the same order.
 */
export function useMadeItemDemandsQuery() {
  const {
    search,
    idFilter,
    projectId,
    itemArticleName,
    statuses,
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
    stepMethods,
    lotIds,
    sortBy,
    sortDir,
  } = storeToRefs(useMadeItemsDemandsFiltersStore())

  function filterParams() {
    const { fabricationMethodIds, inspectionMethodIds } = decodeStepMethods(stepMethods.value)
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
      ...(statuses.value.length > 0 ? { statuses: statuses.value } : {}),
      ...(fabricationMethodIds.length > 0
        ? { process_fabrication_method_id: fabricationMethodIds }
        : {}),
      ...(inspectionMethodIds.length > 0
        ? { process_inspection_method_id: inspectionMethodIds }
        : {}),
      ...(lotIds.value.length > 0 ? { lot_id: lotIds.value } : {}),
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
