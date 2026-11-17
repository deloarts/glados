import { watch, type Ref } from 'vue'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { filterMetaValue } from '@/core/utils/filterMeta'

/**
 * Watches only the named fields of a OpenVue filter meta and calls `onChange`
 * when one of their values changes. A management table uses it twice, once
 * for its typed text filters with a debounced fetch and once for its select
 * filters with an immediate one.
 *
 * The values are compared as a JSON string because OpenVue replaces the
 * whole meta object on every `filterCallback()`, so a plain deep watch would
 * fire for every field whenever any single field changes.
 */
export function useFilterMetaWatch(
  filters: Ref<DataTableFilterMeta>,
  fields: readonly string[],
  onChange: () => void,
): void {
  watch(
    () => JSON.stringify(fields.map((field) => filterMetaValue(filters.value, field))),
    onChange,
  )
}
