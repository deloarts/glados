import { computed, type Ref, type WritableComputedRef } from 'vue'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { filterMetaValue } from '@/core/utils/filterMeta'

/**
 * Writes one field's value as a new filter meta object, as OpenVue's own
 * `filterCallback()` does, so the watchers on the filter meta see the
 * change. The field keeps its match mode, and a new field matches equals.
 */
function writeFilterMetaValue(filters: Ref<DataTableFilterMeta>, field: string, value: unknown): void {
  const meta = filters.value[field]
  const matchMode = typeof meta === 'object' && meta !== null && 'matchMode' in meta ? meta.matchMode : 'equals'
  filters.value = { ...filters.value, [field]: { value: value ?? null, matchMode } }
}

/**
 * One field of an OpenVue filter meta as a plain model, for a filter that
 * sits outside its own column, such as the creator filter that a merged
 * created column carries.
 */
export function useFilterMetaModel<T>(
  filters: Ref<DataTableFilterMeta>,
  field: string,
): WritableComputedRef<T | null, T | null | undefined> {
  return computed({
    get: () => (filterMetaValue(filters.value, field) as T | null | undefined) ?? null,
    set: (value) => writeFilterMetaValue(filters, field, value),
  })
}

/**
 * The same for fields named at render time, as the columns of a catalogue
 * table are. Every set writes the field and then calls `onChange`, which a
 * server side table uses to refetch.
 */
export function useKeyedFilterMetaModel(filters: Ref<DataTableFilterMeta>, onChange?: () => void) {
  function getFilterValue<T>(field: string): T | null {
    return (filterMetaValue(filters.value, field) as T | null | undefined) ?? null
  }

  function setFilterValue(field: string, value: unknown): void {
    writeFilterMetaValue(filters, field, value)
    onChange?.()
  }

  return { getFilterValue, setFilterValue }
}
