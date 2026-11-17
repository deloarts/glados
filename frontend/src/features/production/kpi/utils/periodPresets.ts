// Resolves the KPI period presets to local calendar dates and computes the
// preceding period of the same length for the tile deltas.

import { DAY_MS, addDays, startOfDay, startOfWeek, todayStart } from '@/core/utils/dates'

export type ProductionKpiPeriodPreset =
  | 'this_week'
  | 'last_week'
  | 'this_month'
  | 'last_month'
  | 'last_90_days'
  | 'custom'

// In display order; 'custom' is appended by the Select.
export const PRESET_PERIODS: Exclude<ProductionKpiPeriodPreset, 'custom'>[] = [
  'this_week',
  'last_week',
  'this_month',
  'last_month',
  'last_90_days',
]

const LAST_90_DAYS_SPAN = 90

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0)
}

/** [from, to], both inclusive, for one of the five non-custom presets. */
export function resolvePeriodPreset(
  preset: Exclude<ProductionKpiPeriodPreset, 'custom'>,
  now: Date = new Date(),
): [Date, Date] {
  const today = todayStart(now)
  switch (preset) {
    case 'this_week': {
      const from = startOfWeek(today)
      return [from, addDays(from, 6)]
    }
    case 'last_week': {
      const from = addDays(startOfWeek(today), -7)
      return [from, addDays(from, 6)]
    }
    case 'this_month':
      return [startOfMonth(today), endOfMonth(today)]
    case 'last_month': {
      const lastMonthDay = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      return [startOfMonth(lastMonthDay), endOfMonth(lastMonthDay)]
    }
    case 'last_90_days':
      return [addDays(today, -(LAST_90_DAYS_SPAN - 1)), today]
  }
}

/**
 * The preceding period of the same length, for any range.
 */
export function previousPeriodOf(dateFrom: Date, dateTo: Date): [Date, Date] {
  const spanMs = startOfDay(dateTo).getTime() - startOfDay(dateFrom).getTime()
  const lengthDays = Math.round(spanMs / DAY_MS) + 1
  const prevTo = addDays(startOfDay(dateFrom), -1)
  const prevFrom = addDays(prevTo, -(lengthDays - 1))
  return [prevFrom, prevTo]
}
