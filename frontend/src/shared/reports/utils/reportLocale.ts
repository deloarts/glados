import { i18n } from '@/core/i18n'
import type { AppLocale, Translate } from '@/core/i18n'
import { getDisplayTimezone, localeTag, parseBackendTimestamp, toDateKey } from '@/core/utils/dates'

/**
 * Texts and dates of a report in the language chosen for the export, which
 * may differ from the language of the app. Dates use one fixed format per
 * language instead of each user's date format preset, so a report reads the
 * same whoever exports it.
 */

export type ReportTranslate = Translate

export function reportTranslator(locale: AppLocale): ReportTranslate {
  return (key, params) => i18n.global.t(key, params ?? {}, { locale })
}

/** "9 Oct 2026, 14:05" or "09.10.2026, 14:05", in the tenant's timezone. */
export function formatReportDateTime(value: Date | string, locale: AppLocale): string {
  const date = typeof value === 'string' ? parseBackendTimestamp(value) : value
  return new Intl.DateTimeFormat(localeTag(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: getDisplayTimezone(),
  }).format(date)
}

/** The time of day of an instant, "14:05", in the tenant's timezone. */
export function formatReportTime(value: Date | string, locale: AppLocale): string {
  const date = typeof value === 'string' ? parseBackendTimestamp(value) : value
  return new Intl.DateTimeFormat(localeTag(locale), { timeStyle: 'short', timeZone: getDisplayTimezone() }).format(date)
}

/** The calendar day of an instant in the tenant's timezone, "2026-10-09". */
export function reportDayKey(value: Date | string): string {
  const date = typeof value === 'string' ? parseBackendTimestamp(value) : value
  return date.toLocaleDateString('en-CA', { timeZone: getDisplayTimezone() })
}

/** A calendar date "2026-10-09" as "9 Oct 2026" or "09.10.2026"; anything else as it is. */
export function formatReportDate(value: string, locale: AppLocale): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return value
  return new Intl.DateTimeFormat(localeTag(locale), { dateStyle: 'medium', timeZone: 'UTC' }).format(
    new Date(`${value}T00:00:00Z`),
  )
}

/** A file name from a report title: letters, digits and dashes only. */
export function reportFileName(title: string, date: Date): string {
  const slug = title
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^A-Za-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
  return `${slug || 'report'}_${toDateKey(date)}.pdf`
}
