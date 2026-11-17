import type { DataTableFilterMeta } from 'openvue/datatable'

/**
 * Reading an OpenVue DataTable filter model. A field's entry is either a
 * plain `{ value, matchMode }` meta or an operator meta with constraints,
 * and only the plain kind carries a value of its own.
 */

/** The value of one field's filter, or null when it has none. */
export function filterMetaValue(filters: DataTableFilterMeta, field: string): unknown {
  const meta = filters[field]
  return typeof meta === 'object' && meta !== null && 'value' in meta ? meta.value : null
}

/**
 * True for a filter value that narrows the rows: not null, undefined or
 * empty text, and for a range or multi-select at least one picked entry.
 */
function isFilterValueSet(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return false
  return !Array.isArray(value) || value.some((entry) => entry !== null && entry !== undefined)
}

/**
 * Whether any field of the filter model holds a value, so a view can enable
 * its Clear button while only a column filter is set.
 */
export function hasActiveFilterMeta(filters: DataTableFilterMeta): boolean {
  return Object.values(filters).some(
    (meta) =>
      typeof meta === 'object' && meta !== null && 'value' in meta && isFilterValueSet(meta.value),
  )
}
