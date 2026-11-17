/**
 * Custom OpenVue match modes for tables that filter rows in the browser.
 *
 * OpenVue's built-in modes cover text and single-bound comparisons, but a
 * row filter cell for a date or number column holds a whole range, so these
 * two modes take a `[from, to]` pair as the filter value. Either bound may be
 * null to leave that side open, and both are inclusive. A row whose own value
 * is empty never matches an active range, the same way OpenVue's CONTAINS
 * treats a null cell.
 *
 * The modes are registered with OpenVue's global FilterService when this
 * module is first imported, so a table that references `RowFilterMatchMode`
 * can never end up with an unregistered mode.
 */
import { FilterService } from '@openvue/core/api'

import { dateToParam, toDayKey } from '@/core/utils/dates'

export const RowFilterMatchMode = {
  DATE_RANGE: 'gladosDateRange',
  NUMBER_RANGE: 'gladosNumberRange',
} as const

/**
 * What a date range row filter hands over: the DatePicker's range payload,
 * which may be a partial array while the second day is still being picked.
 */
export type DateRangeFilterValue = Date | Array<Date | null> | null | undefined

export type NumberRangeFilterValue = [number | null, number | null] | null | undefined

/**
 * Whether a calendar date or instant falls inside the picked days. Instants
 * are compared by the day they fall on in the tenant's timezone, so a delivery
 * stamped late in the evening still counts for the day the table shows.
 */
export function matchesDateRange(value: unknown, filter: DateRangeFilterValue): boolean {
  const [from, to] = Array.isArray(filter) ? filter : [filter ?? null, null]
  if (!from && !to) return true
  if (typeof value !== 'string' || value === '') return false
  const day = toDayKey(value)
  const fromKey = dateToParam(from ?? null)
  const toKey = dateToParam(to ?? null)
  if (fromKey && day < fromKey) return false
  if (toKey && day > toKey) return false
  return true
}

export function matchesNumberRange(value: unknown, filter: NumberRangeFilterValue): boolean {
  const [min, max] = filter ?? [null, null]
  if (min === null && max === null) return true
  if (typeof value !== 'number' || Number.isNaN(value)) return false
  if (min !== null && value < min) return false
  if (max !== null && value > max) return false
  return true
}

/**
 * Whether any row filter holds a value, so a view can enable its Clear
 * button while only a column filter is set.
 */
export { hasActiveFilterMeta as hasActiveRowFilter } from '@/core/utils/filterMeta'

FilterService.register(RowFilterMatchMode.DATE_RANGE, matchesDateRange)
FilterService.register(RowFilterMatchMode.NUMBER_RANGE, matchesNumberRange)
