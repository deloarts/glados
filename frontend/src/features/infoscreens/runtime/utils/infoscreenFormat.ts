import type { AppLocale } from '@/core/i18n'
import {
  formatISODate,
  formatTimeInZone,
  getDisplayTimezone,
  localeTag,
  parseBackendTimestamp,
} from '@/core/utils/dates'

import type { InfoscreenHoliday } from '../types/infoscreenFeed'

type HasKey = (key: string) => boolean
type Translate = (key: string) => string
type TranslatePlural = (key: string, plural: number) => string

/**
 * A backend status value in words, from the first namespace that knows it.
 * An unknown value is shown as the server sent it, with the underscores as
 * spaces, rather than as a raw translation key.
 */
export function statusLabel(t: Translate, te: HasKey, status: string, prefixes: string[]): string {
  for (const prefix of prefixes) {
    const key = `${prefix}.${status}`
    if (te(key)) return t(key)
  }
  return status.replace(/_/g, ' ')
}

/** A quantity with at most two decimals in the UI language, with its unit when given. */
export function formatQuantity(value: number | null, unit: string | null = null): string | null {
  if (value === null || !Number.isFinite(value)) return null
  const number = new Intl.NumberFormat(localeTag(), { maximumFractionDigits: 2 }).format(value)
  return unit ? `${number} ${unit}` : number
}

/** A calendar date or instant in the display date format, or null. */
export function formatDay(iso: string | null): string | null {
  return iso ? formatISODate(iso) : null
}

/** The 24-hour time of a date in the display timezone. */
export function formatClockTime(date: Date): string {
  try {
    return formatTimeInZone(date, getDisplayTimezone())
  } catch {
    return formatTimeInZone(date, 'UTC')
  }
}

/** The 24-hour time an API instant shows in the display timezone, or null. */
export function formatInstantTime(iso: string | null): string | null {
  return iso ? formatClockTime(parseBackendTimestamp(iso)) : null
}

/** Whole days from today (local) to a calendar date, negative in the past. */
export function daysUntil(isoDate: string, now: Date): number {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  const target = Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((target - today) / 86_400_000)
}

/** The parts of a label that are set, joined with a middle dot. */
export function joinParts(...parts: (string | null | undefined)[]): string {
  return parts.filter((part): part is string => !!part).join(' · ')
}

/** The display timezone, or UTC when the browser does not know it. */
export function displayZone(): string {
  try {
    return new Intl.DateTimeFormat('en-GB', { timeZone: getDisplayTimezone() }).resolvedOptions()
      .timeZone
  } catch {
    return 'UTC'
  }
}

/** Hours and minutes ("14:32") and the seconds of a clock in the display timezone. */
export function clockParts(date: Date): { hoursMinutes: string; seconds: string } {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: displayZone(),
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? '00'
  return { hoursMinutes: `${part('hour')}:${part('minute')}`, seconds: part('second') }
}

/** The weekday and full date in the UI language, such as "Friday, 30 October 2026". */
export function longDateLabel(date: Date, locale: AppLocale): string {
  return new Intl.DateTimeFormat(localeTag(locale), {
    timeZone: displayZone(),
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

/** A holiday's name, its date and how far away it is. */
export function holidayLabel(holiday: InfoscreenHoliday, now: Date, t: TranslatePlural) {
  const days = Math.max(0, daysUntil(holiday.date, now))
  return {
    name: holiday.name,
    date: formatDay(holiday.date),
    when: t('infoscreenRuntime.widgets.clock.inDays', days),
  }
}

/** Hours (0 to 23), minutes and seconds of a clock in the display timezone. */
export function clockNumbers(date: Date): { hours: number; minutes: number; seconds: number } {
  const { hoursMinutes, seconds } = clockParts(date)
  const [hours, minutes] = hoursMinutes.split(':').map(Number)
  return { hours: hours ?? 0, minutes: minutes ?? 0, seconds: Number(seconds) }
}

/** Whole days from the calendar day `fromKey` to `toKey`, both YYYY-MM-DD. */
export function daysBetween(fromKey: string, toKey: string): number {
  const utc = (key: string) => {
    const [year, month, day] = key.slice(0, 10).split('-').map(Number)
    return Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)
  }
  return Math.round((utc(toKey) - utc(fromKey)) / 86_400_000)
}

/** The weekday of a calendar date in the UI language, such as "Thursday". */
export function weekdayLabel(isoDate: string, locale: AppLocale): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  return new Intl.DateTimeFormat(localeTag(locale), { weekday: 'long', timeZone: 'UTC' }).format(
    new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)),
  )
}
