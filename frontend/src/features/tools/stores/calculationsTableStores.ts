import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import {
  createDocumentTableStores,
  documentTableFilter,
} from '@/shared/stores/createDocumentTableStores'
import type { DocumentTableContext } from '@/shared/stores/createDocumentTableStores'
import type { CalculationSortBy } from '../types/calculation'

/**
 * The state behind a calculations table, built by createDocumentTableStores.
 * Only the page sets any of it; the Calculations tabs of a project and of a
 * product get their own instances, which stay at the defaults and which
 * their plain tables ignore.
 */

export type CalculationsContext = DocumentTableContext

export type CalculationGroupBy = 'tool' | 'owner' | 'status'

/** The filter row's fields; the title filter is sent as the server search. */
export function createEmptyCalculationFilters(): DataTableFilterMeta {
  return {
    title: { value: null, matchMode: FilterMatchMode.CONTAINS },
    tool: { value: null, matchMode: FilterMatchMode.EQUALS },
    owner: { value: null, matchMode: FilterMatchMode.EQUALS },
    status: { value: null, matchMode: FilterMatchMode.EQUALS },
    author: { value: null, matchMode: FilterMatchMode.EQUALS },
  }
}

export const useCalculationsTableStores = createDocumentTableStores<CalculationGroupBy, CalculationSortBy>(
  'calculations',
  createEmptyCalculationFilters,
)

/** The value of one filter of the row, or null when it is empty. */
export const calculationFilter = documentTableFilter
