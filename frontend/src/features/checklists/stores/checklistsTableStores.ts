import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import {
  createDocumentTableStores,
  documentTableFilter,
} from '@/shared/stores/createDocumentTableStores'
import type { DocumentTableContext } from '@/shared/stores/createDocumentTableStores'
import type { ChecklistSortBy } from '../types/checklist'

/**
 * The state behind a checklists table, built by createDocumentTableStores.
 * Only the page sets any of it; the Checklists tabs of a project and of a
 * product get their own instances, which stay at the defaults and which
 * their plain tables ignore.
 */

export type ChecklistsContext = DocumentTableContext

export type ChecklistGroupBy = 'type' | 'owner' | 'verdict' | 'status'

/** The filter row's fields; the title filter is sent as the server search. */
export function createEmptyChecklistFilters(): DataTableFilterMeta {
  return {
    title: { value: null, matchMode: FilterMatchMode.CONTAINS },
    type: { value: null, matchMode: FilterMatchMode.EQUALS },
    owner: { value: null, matchMode: FilterMatchMode.EQUALS },
    verdict: { value: null, matchMode: FilterMatchMode.EQUALS },
    status: { value: null, matchMode: FilterMatchMode.EQUALS },
    author: { value: null, matchMode: FilterMatchMode.EQUALS },
  }
}

export const useChecklistsTableStores = createDocumentTableStores<ChecklistGroupBy, ChecklistSortBy>(
  'checklists',
  createEmptyChecklistFilters,
)

/** The value of one filter of the row, or null when it is empty. */
export const checklistFilter = documentTableFilter
