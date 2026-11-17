import { getCurrentInstance, inject } from 'vue'
import type { InjectionKey } from 'vue'

import { getDisplayTimezone, localeTag } from '@/core/utils/dates'
import type { AppLocale } from '@/core/i18n'

/**
 * Pins the formatting of a whole component subtree to one locale, for
 * components rendered outside the app in another language, such as a sketch
 * drawn into a PDF report. Provided on the app that renders them.
 */
export const FORMAT_LOCALE_KEY: InjectionKey<AppLocale> = Symbol('formatLocale')

/**
 * Number, date and time formatting pinned to the app's active UI language.
 *
 * A bare `value.toFixed(1)`, `value.toLocaleString()`, `date.toLocaleDateString()`
 * or `date.toLocaleTimeString()` formats using the browser's own language,
 * which drifts from the language the user actually picked in Glados, a
 * German-OS visitor using the English UI still sees "1.234,5" instead of
 * "1,234.5". Every formatter here goes through `Intl.NumberFormat` /
 * `Intl.DateTimeFormat` with `localeTag()` instead, so the output always
 * matches the UI language.
 *
 * For an API date or time value, prefer `core/utils/dates.ts`'s
 * `formatISODate` / `formatISODateTime` / `formatISOTime` instead: those
 * also honour the user's saved date-format preset, which this composable
 * does not attempt to duplicate. This one is for a plain `Date`/number that
 * carries no such preference, a client-side timestamp, a chart value, or any
 * other number computed for display. Dates and times render in the tenant's
 * display timezone unless the options name another `timeZone`.
 *
 * `locale` optionally pins the output to one specific locale regardless of
 * the current UI language, mirroring `localeTag`'s own override parameter
 * and `formatPrice`'s same pattern (see dates.ts).
 */
export function useLocaleFormat(locale?: AppLocale) {
  // Outside a component (a plain function building a report) nothing can be
  // injected, and asking would only log a warning.
  const pinned = locale ?? (getCurrentInstance() ? inject(FORMAT_LOCALE_KEY, undefined) : undefined)
  const tag = () => localeTag(pinned)

  function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
    return new Intl.NumberFormat(tag(), options).format(value)
  }

  // The display timezone first, so an explicit `timeZone` in the options wins.
  function dateTimeFormat(options: Intl.DateTimeFormatOptions | undefined): Intl.DateTimeFormat {
    return new Intl.DateTimeFormat(tag(), { timeZone: getDisplayTimezone(), ...options })
  }

  function formatDate(value: Date | number, options?: Intl.DateTimeFormatOptions): string {
    return dateTimeFormat(options).format(value)
  }

  function formatTime(value: Date | number, options?: Intl.DateTimeFormatOptions): string {
    return dateTimeFormat(options ?? { timeStyle: 'medium' }).format(value)
  }

  function formatDateTime(value: Date | number, options?: Intl.DateTimeFormatOptions): string {
    return dateTimeFormat(options ?? { dateStyle: 'medium', timeStyle: 'short' }).format(value)
  }

  return { formatNumber, formatDate, formatTime, formatDateTime }
}
