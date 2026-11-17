import { ref } from 'vue'
import type { Ref } from 'vue'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { filterMetaValue, hasActiveFilterMeta } from '@/core/utils/filterMeta'
import { createCatalogueViewStore } from './createCatalogueViewStore'
import { createFiltersStore } from './createFiltersStore'

/**
 * The state behind a table of saved documents such as calculations or
 * checklists: grouping, sorting and the actions column (view store), and the
 * column filters (filters store). Only the page sets any of it; the tabs of a
 * project and of a product get their own instances, which stay at the
 * defaults and which their plain tables ignore.
 */

export type DocumentTableContext = 'page' | 'project' | 'product'

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type DocumentTableFilterFields = {
  filters: DataTableFilterMeta
}

type DocumentTableFilterExtra = {
  /** Bumped by Sync and after a delete, to reload the current page. */
  refreshTrigger: Ref<number>
  triggerRefresh: () => void
}

/**
 * Builds the view and filters stores of every context once, with the ids
 * `<prefix>View-<context>` and `<prefix>Filters-<context>`, and returns the
 * accessor for one context's pair.
 */
export function createDocumentTableStores<TGroupBy extends string, TSortBy extends string>(
  prefix: string,
  createEmptyFilters: () => DataTableFilterMeta,
) {
  function createStores(context: DocumentTableContext) {
    return {
      view: createCatalogueViewStore<TGroupBy, TSortBy>(`${prefix}View-${context}`),
      filters: createFiltersStore<DocumentTableFilterFields, never, false, DocumentTableFilterExtra>(
        `${prefix}Filters-${context}`,
        {
          // The DataTable mutates the filter objects in place, so every reset
          // needs fresh ones.
          defaults: () => ({ filters: createEmptyFilters() }),
          sortable: false,
          isActive: (fields) => hasActiveFilterMeta(fields.filters),
          extend: () => {
            const refreshTrigger = ref(0)
            return {
              state: { refreshTrigger, triggerRefresh: () => (refreshTrigger.value += 1) },
            }
          },
        },
      ),
    }
  }

  const stores = {
    page: createStores('page'),
    project: createStores('project'),
    product: createStores('product'),
  } satisfies Record<DocumentTableContext, ReturnType<typeof createStores>>

  return function useDocumentTableStores(context: DocumentTableContext) {
    return { view: stores[context].view(), filters: stores[context].filters() }
  }
}

/** The value of one filter of the row, or null when it is empty. */
export function documentTableFilter(filters: DataTableFilterMeta, field: string): unknown {
  const value = filterMetaValue(filters, field)
  return value === undefined || value === '' ? null : value
}
