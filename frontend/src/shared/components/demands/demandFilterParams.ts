import type { Ref } from 'vue'

import { dateToParam as toDateParam } from '@/core/utils/dates'

/**
 * The filter refs of a demands filters store that map to the same query
 * params on every demand list endpoint. The optional ones exist on the bought
 * and made item tables only.
 */
export interface CommonDemandFilterRefs {
  idFilter: Ref<number | null>
  projectId: Ref<number | null>
  creatorFilter: Ref<number | null>
  showFulfilled: Ref<boolean>
  showCanceled: Ref<boolean>
  desiredFrom: Ref<Date | null>
  desiredTo: Ref<Date | null>
  notFullyAllocatedOnly: Ref<boolean>
  bucketIds: Ref<number[]>
  includeUnbucketed: Ref<boolean>
  search?: Ref<string>
  itemArticleName?: Ref<string>
  highPriorityFilter?: Ref<boolean | null>
  createdFrom?: Ref<Date | null>
  createdTo?: Ref<Date | null>
}

export interface CommonDemandFilterParams {
  search?: string
  ids?: number[]
  project_id?: number
  item_article_name?: string
  high_priority?: boolean
  creator_id?: number
  ignore_fulfilled?: boolean
  ignore_canceled?: boolean
  desired_from?: string
  desired_to?: string
  created_from?: string
  created_to?: string
  not_fully_allocated?: boolean
  bucket_id?: number[]
  include_unbucketed?: boolean
}

/**
 * The query params the demand tables share, each sent only while its filter
 * is set. Fulfilled and canceled demands are left out unless their toggle is
 * on. The family's own params (status, item and lookup filters) stay with
 * its table.
 */
export function buildCommonDemandFilterParams(refs: CommonDemandFilterRefs): CommonDemandFilterParams {
  const { search, itemArticleName, highPriorityFilter, createdFrom, createdTo } = refs
  return {
    ...(search?.value ? { search: search.value } : {}),
    ...(refs.idFilter.value !== null ? { ids: [refs.idFilter.value] } : {}),
    ...(refs.projectId.value !== null ? { project_id: refs.projectId.value } : {}),
    ...(itemArticleName?.value ? { item_article_name: itemArticleName.value } : {}),
    ...(highPriorityFilter && highPriorityFilter.value !== null
      ? { high_priority: highPriorityFilter.value }
      : {}),
    ...(refs.creatorFilter.value ? { creator_id: refs.creatorFilter.value } : {}),
    ...(!refs.showFulfilled.value ? { ignore_fulfilled: true } : {}),
    ...(!refs.showCanceled.value ? { ignore_canceled: true } : {}),
    ...(refs.desiredFrom.value
      ? { desired_from: toDateParam(refs.desiredFrom.value) ?? undefined }
      : {}),
    ...(refs.desiredTo.value ? { desired_to: toDateParam(refs.desiredTo.value) ?? undefined } : {}),
    ...(createdFrom?.value ? { created_from: toDateParam(createdFrom.value) ?? undefined } : {}),
    ...(createdTo?.value ? { created_to: toDateParam(createdTo.value) ?? undefined } : {}),
    // Set while a Manage panel is open, narrowing to rows it can act on.
    ...(refs.notFullyAllocatedOnly.value ? { not_fully_allocated: true } : {}),
    ...(refs.bucketIds.value.length > 0 ? { bucket_id: refs.bucketIds.value } : {}),
    ...(refs.includeUnbucketed.value ? { include_unbucketed: true } : {}),
  }
}
