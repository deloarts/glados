import { localeTag } from '@/core/utils/dates'
import { getDisplayCurrency } from '@/core/utils/currency'
import { formatDuration } from '@/shared/utils/formatDuration'

import type { TimeTrackingAccountFormat } from '../types/timeTrackingTypes'

/**
 * Renders a time tracking account value by the account's own format, so
 * accounts stay generic: the view never knows which account is vacation,
 * overtime or a counter, it only knows how each one is written. Durations
 * are seconds, shown as h:mm or as decimal hours; `count` is a whole
 * number, `decimal` has two places, `money` is in cents, and `raw` (or a
 * format this build does not know) is the number as sent.
 */
export function formatAccountValue(value: number, format: TimeTrackingAccountFormat): string {
  const number = (fraction: number) =>
    new Intl.NumberFormat(localeTag(), {
      minimumFractionDigits: fraction,
      maximumFractionDigits: fraction,
    })
  switch (format) {
    case 'duration_clock':
      return formatDuration(value)
    case 'duration_hours':
      return number(2).format(value / 3600)
    case 'count':
      return number(0).format(Math.round(value))
    case 'decimal':
      return number(2).format(value)
    case 'money':
      return new Intl.NumberFormat(localeTag(), {
        style: 'currency',
        currency: getDisplayCurrency(),
      }).format(value / 100)
    default:
      return String(value)
  }
}
