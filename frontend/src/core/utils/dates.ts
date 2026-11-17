import { ref } from 'vue'

import { i18n } from '@/core/i18n'
import { getEmptyPlaceholder } from './emptyValue'
import type { AppLocale } from '@/core/i18n'

/**
 * BCP-47 tag for a UI language: the one canonical `AppLocale` → tag mapping,
 * used for anything `Intl` needs a locale for but this file's own
 * preset-driven formatters don't cover (weekday/month names, chart tick
 * labels, `Intl.NumberFormat`).
 *
 * Defaults to the current UI language unless an explicit one is given, because some
 * callers render in a fixed language regardless of the viewer's own (mirrors
 * `formatPrice`'s same locale-override pattern).
 *
 * Safe to import i18n here: its locale modules import nothing, so there is no
 * cycle back into this file.
 */
export function localeTag(locale?: AppLocale): string {
  const resolved = locale ?? (i18n.global.locale.value as AppLocale)
  return resolved === 'deAT' ? 'de-AT' : 'en-GB'
}

// ── Two kinds of value, deliberately distinguished ────────────────────
//
// The API sends two shapes that must NOT be treated alike:
//
//   1. INSTANTS, "2026-08-06T14:32:11.123456+00:00". Something that
//      happened at a point in time (created, changed, ordered_date,
//      delivery_date, ready_for_pickup_date, actual_start/end, ...). These
//      are stored UTC and must be rendered in the tenant's timezone.
//
//   2. CALENDAR DATES, "2026-08-06". A day a human picked off a date
//      picker (expected_delivery_date, required_delivery_date, not_before,
//      completion_date, provision_date, ...). These have no time and no
//      timezone: 6 August is 6 August everywhere. Shifting one into a
//      timezone is how you get an off-by-one day.
//
// An instant contains "T", so the formatters branch on shape instead of
// every caller declaring the kind.

/**
 * The timezone timestamps are rendered in: the tenant's default timezone
 * from the general settings (an IANA name like "Europe/Vienna"), applied by
 * hostStore once /host/capabilities answers. The whole app uses this one
 * zone, so every user sees the same wall clock whatever their browser
 * reports.
 *
 * A ref rather than a plain module variable so that templates calling the
 * formatters below re-render when an admin changes the setting.
 *
 * null = the capabilities have not answered yet, so fall back to whatever
 * the browser reports.
 */
const displayTimezone = ref<string | null>(null)

export function setDisplayTimezone(timezone: string | null): void {
  displayTimezone.value = timezone || null
}

export function getDisplayTimezone(): string {
  return displayTimezone.value || Intl.DateTimeFormat().resolvedOptions().timeZone
}

// ── Date format preference ────────────────────────────────────────────
//
// A closed set of presets, mirroring the backend DateFormat enum. Presets
// rather than a locale tag (which would also drag month names and week start
// along) or a free-form pattern (which needs a validator and lets a user save
// something unrenderable).
//
// PRESENTATION ONLY. `dateToParam` at the bottom of this file, the one that
// builds API query params and request bodies, is deliberately NOT affected:
// the API speaks YYYY-MM-DD, and letting a display preference leak into a
// filter bound would silently return the wrong rows.

export const DATE_FORMATS = ['iso', 'dmy_dot', 'dmy_slash', 'mdy_slash', 'd_mon_y'] as const

export type DateFormatPreset = (typeof DATE_FORMATS)[number]

const DEFAULT_DATE_FORMAT: DateFormatPreset = 'iso'

/** OpenVue DatePicker token per preset, so inputs accept what the UI shows. */
const PICKER_TOKENS: Record<DateFormatPreset, string> = {
  iso: 'yy-mm-dd',
  dmy_dot: 'dd.mm.yy',
  dmy_slash: 'dd/mm/yy',
  mdy_slash: 'mm/dd/yy',
  d_mon_y: 'dd M yy',
}

const displayDateFormat = ref<DateFormatPreset>(DEFAULT_DATE_FORMAT)

function isDateFormatPreset(value: unknown): value is DateFormatPreset {
  return typeof value === 'string' && (DATE_FORMATS as readonly string[]).includes(value)
}

export function setDisplayDateFormat(format: string | null | undefined): void {
  // An unknown preset, such as a hand-edited payload, falls back rather than
  // rendering dates as "undefined".
  displayDateFormat.value = isDateFormatPreset(format) ? format : DEFAULT_DATE_FORMAT
}

export function getDisplayDateFormat(): DateFormatPreset {
  return displayDateFormat.value
}

/** The OpenVue `dateFormat` token matching the current preference. */
export function getPickerDateFormat(): string {
  return PICKER_TOKENS[displayDateFormat.value]
}

/** True for a bare "YYYY-MM-DD", a calendar date, not an instant. */
export function isCalendarDate(value: string): boolean {
  return !value.includes('T')
}

// `new Date(str)` reads a timestamp without offset as local time, so a
// missing offset is treated as UTC. A bare date is already read as UTC.
export function parseBackendTimestamp(value: string): Date {
  const hasTimezone = /Z$|[+-]\d{2}:?\d{2}$/.test(value)
  return new Date(value.includes('T') && !hasTimezone ? `${value}Z` : value)
}

/** A moment's calendar and clock fields on the wall clock of one timezone. */
export interface ZonedParts {
  year: string
  month: string
  day: string
  hour: string
  minute: string
}

/**
 * The year, month, day, hour and minute `date` shows on the wall clock of
 * `timeZone`, as zero-padded strings (hours 00 to 23).
 *
 * `formatToParts` rather than string surgery so the timezone shift is done by
 * Intl. Throws a RangeError for a timezone the browser does not know, so a
 * caller that takes the zone from user input catches it.
 */
export function zonedParts(date: Date, timeZone: string): ZonedParts {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)

  const find = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? ''

  return {
    year: find('year'),
    month: find('month'),
    day: find('day'),
    hour: find('hour'),
    minute: find('minute'),
  }
}

/**
 * Minutes since midnight of `date` on the wall clock of `timeZone`, or null
 * when the timezone is not one the browser knows.
 */
export function minutesSinceMidnight(date: Date, timeZone: string): number | null {
  try {
    const { hour, minute } = zonedParts(date, timeZone)
    const hours = Number(hour)
    const minutes = Number(minute)
    if (hour === '' || minute === '' || !Number.isInteger(hours) || !Number.isInteger(minutes)) {
      return null
    }
    return hours * 60 + minutes
  } catch {
    return null
  }
}

/**
 * The 24-hour time of day ("14:32") `date` shows in `timeZone`. Throws a
 * RangeError for a timezone the browser does not know.
 */
export function formatTimeInZone(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(date)
}

/**
 * The calendar Y/M/D a value lands on, as strings, resolved in the right
 * frame: the display timezone for an instant, verbatim (UTC-pinned) for a
 * calendar date so the day off the wire is the day shown.
 */
function dateParts(iso: string): { year: string; month: string; day: string } {
  const timeZone = isCalendarDate(iso) ? 'UTC' : getDisplayTimezone()
  const { year, month, day } = zonedParts(parseBackendTimestamp(iso), timeZone)
  return { year, month, day }
}

/** Name of month number `month` (1 to 12) in the UI language. */
export function monthName(month: number, style: 'long' | 'short' = 'short'): string {
  return new Intl.DateTimeFormat(localeTag(), { month: style, timeZone: 'UTC' }).format(
    Date.UTC(2000, month - 1, 1),
  )
}

/** Name of the weekday a local `Date` falls on, in the UI language. */
export function weekdayName(date: Date, style: 'long' | 'short' = 'short'): string {
  return new Intl.DateTimeFormat(localeTag(), { weekday: style }).format(date)
}

/** Short month name for the `d_mon_y` preset, in the user's UI language. */
function shortMonthName(iso: string): string {
  return new Intl.DateTimeFormat(localeTag(), {
    timeZone: isCalendarDate(iso) ? 'UTC' : getDisplayTimezone(),
    month: 'short',
  }).format(parseBackendTimestamp(iso))
}

/**
 * Renders a value as a date using an explicitly given preset.
 *
 * Pure, it reads no preference state, so it is safe to call from inside a
 * `computed` (e.g. a settings screen previewing every preset at once).
 * Formatting with the *current* preference is `formatISODate` below.
 *
 * Assembled from parts rather than handed to `toLocaleDateString`, so a preset
 * means exactly one output shape regardless of the browser's own locale, the
 * reason this is a preference and not a locale passthrough.
 */
export function formatISODateAs(iso: string, preset: DateFormatPreset): string {
  const { year, month, day } = dateParts(iso)
  switch (preset) {
    case 'dmy_dot':
      return `${day}.${month}.${year}`
    case 'dmy_slash':
      return `${day}/${month}/${year}`
    case 'mdy_slash':
      return `${month}/${day}/${year}`
    case 'd_mon_y':
      return `${day} ${shortMonthName(iso)} ${year}`
    default:
      return `${year}-${month}-${day}`
  }
}

/** As `formatISODateAs`, plus the 24-hour time for an instant. */
export function formatISODateTimeAs(iso: string, preset: DateFormatPreset): string {
  if (isCalendarDate(iso)) return formatISODateAs(iso, preset)
  return `${formatISODateAs(iso, preset)} ${formatISOTime(iso)}`
}

/** Renders a value as a date, using the user's current format preset. */
export function formatISODate(iso: string): string {
  return formatISODateAs(iso, getDisplayDateFormat())
}

/**
 * Renders an instant as date + time-of-day in the display timezone.
 *
 * A calendar date has no time to show, so it falls through to
 * `formatISODate` rather than inventing a 00:00.
 */
export function formatISODateTime(iso: string): string {
  return formatISODateTimeAs(iso, getDisplayDateFormat())
}

/**
 * Time of day only, in the display timezone. Empty for a calendar date.
 *
 * Always 24-hour: `hourCycle: 'h23'` rather than the browser's preference,
 * so a US-locale browser doesn't render AM/PM while a European one shows
 * 14:32 for the same record.
 */
export function formatISOTime(iso: string): string {
  if (isCalendarDate(iso)) return ''
  return formatTimeInZone(parseBackendTimestamp(iso), getDisplayTimezone())
}

/**
 * The YYYY-MM-DD day an instant falls on **in the display timezone**, the
 * key to group, bucket, or compare by day.
 *
 * Use this instead of `dateToParam(parseBackendTimestamp(iso))`, which
 * answers the same question in the browser's timezone and truncates via
 * local date parts.
 */
export function toDayKey(iso: string): string {
  if (isCalendarDate(iso)) return iso
  // 'en-CA' renders as YYYY-MM-DD; the timeZone option does the shifting.
  return parseBackendTimestamp(iso).toLocaleDateString('en-CA', {
    timeZone: getDisplayTimezone(),
  })
}

/**
 * Table/detail display pair for a nullable API value.
 *
 * Dense tables show the day and put the exact instant in a `title`, so a
 * column stays narrow but the time of day is one hover away, the whole point
 * of the event columns carrying a time at all.
 */
export function formatDateOrDash(iso: string | null | undefined): string {
  return iso ? formatISODate(iso) : getEmptyPlaceholder()
}

export function formatDateTimeOrDash(iso: string | null | undefined): string {
  return iso ? formatISODateTime(iso) : getEmptyPlaceholder()
}

/** Empty (not a dash) so an absent value produces no tooltip at all. */
export function formatDateTimeOrEmpty(iso: string | null | undefined): string {
  return iso ? formatISODateTime(iso) : ''
}

// ── Local calendar arithmetic ─────────────────────────────────────────
//
// For Date objects that already sit on the browser's local calendar (picker
// values, day columns, period bounds), not for API strings, which go through
// `toLocalDayStart` first.

/** Milliseconds in a 24-hour day, for spans and day indexes measured in time. */
export const DAY_MS = 24 * 60 * 60 * 1000

/** A copy of `date` at local midnight. */
export function startOfDay(date: Date): Date {
  const copy = new Date(date)
  copy.setHours(0, 0, 0, 0)
  return copy
}

/**
 * A copy of `date` moved by `count` calendar days, keeping its time of day.
 * Steps on the calendar rather than by `DAY_MS`, so a daylight saving change
 * in between does not shift the result by an hour.
 */
export function addDays(date: Date, count: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + count)
  return result
}

/** Local midnight on the Monday of the week `date` falls in. */
export function startOfWeek(date: Date): Date {
  const day = date.getDay()
  return addDays(startOfDay(date), (day === 0 ? -6 : 1) - day)
}

/** Local midnight on the Sunday that ends the week `date` falls in. */
export function endOfWeek(date: Date): Date {
  return addDays(startOfWeek(date), 6)
}

/** The earlier of two dates, treating null (no date) as no constraint. */
export function earlierDate(a: Date | null, b: Date | null): Date | null {
  if (!a) return b
  if (!b) return a
  return a.getTime() <= b.getTime() ? a : b
}

/**
 * A local `Date` at midnight on the day the value falls on, resolved in the
 * display timezone.
 *
 * For anything that buckets, spans, or plots by day (Gantt bars, day-index
 * charts, "within the last 30 days" windows): it puts instants and calendar
 * dates on the same footing, so a bar derived from a timestamped
 * delivery_date lines up with one derived from a date-only
 * expected_delivery_date instead of sitting some hours off.
 */
export function toLocalDayStart(iso: string): Date {
  const [y, m, d] = toDayKey(iso).split('-').map(Number)
  return new Date(y ?? 0, (m ?? 1) - 1, d ?? 1)
}

/**
 * Today's YYYY-MM-DD in the display timezone, so "today" is the same day
 * for every user however their browser's clock is set.
 */
export function todayKey(now: Date = new Date()): string {
  return toDayKey(now.toISOString())
}

/**
 * A local `Date` at midnight on today's day in the display timezone, the
 * "today" to compare against values put through `toLocalDayStart`.
 */
export function todayStart(now: Date = new Date()): Date {
  return toLocalDayStart(now.toISOString())
}

// ── Pickers on the tenant's wall clock ────────────────────────────────
//
// A DatePicker shows and edits the fields of a local `Date`, which is the
// browser's wall clock. These helpers move an instant onto the display
// timezone's wall clock and back, so a picker with a time shows and takes
// the tenant's time even when the browser sits in another zone.

/** How far the wall clock of `timeZone` runs ahead of UTC at `date`, in milliseconds. */
function zoneOffsetMs(date: Date, timeZone: string): number {
  const { year, month, day, hour, minute } = zonedParts(date, timeZone)
  const wallClock = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
  )
  return wallClock - Math.floor(date.getTime() / 60000) * 60000
}

/**
 * The instant at which the display timezone's wall clock reads the given
 * fields, passed as if they were UTC. The offset is read twice, the second
 * time at the corrected instant, so a daylight saving change near that time
 * still lands on the right hour.
 */
function wallClockToInstant(wallClockAsUtc: number): Date {
  const timeZone = getDisplayTimezone()
  let offset = zoneOffsetMs(new Date(wallClockAsUtc), timeZone)
  offset = zoneOffsetMs(new Date(wallClockAsUtc - offset), timeZone)
  return new Date(wallClockAsUtc - offset)
}

/**
 * A picker value for an instant: a local `Date` whose fields read what the
 * display timezone's wall clock shows at that instant.
 */
export function instantToPickerDate(value: Date | string): Date {
  const date = typeof value === 'string' ? parseBackendTimestamp(value) : value
  const { year, month, day, hour, minute } = zonedParts(date, getDisplayTimezone())
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    date.getUTCSeconds(),
    date.getUTCMilliseconds(),
  )
}

/**
 * A local `Date` for an API value on the tenant's wall clock: a calendar date
 * at local midnight on that very day, an instant with the fields the display
 * timezone shows. The shape for a picker, a timeline bar or anything else
 * that reads a `Date`'s local fields.
 */
export function toWallClockDate(value: string): Date {
  return isCalendarDate(value) ? toLocalDayStart(value) : instantToPickerDate(value)
}

/** The instant a picker value names, reading its fields on the display timezone's wall clock. */
export function pickerDateToInstant(picked: Date): Date {
  return wallClockToInstant(
    Date.UTC(
      picked.getFullYear(),
      picked.getMonth(),
      picked.getDate(),
      picked.getHours(),
      picked.getMinutes(),
      picked.getSeconds(),
      picked.getMilliseconds(),
    ),
  )
}

/**
 * The last millisecond of the calendar day a date-only picker value shows,
 * on the display timezone's wall clock. A day picked as an expiry then lasts
 * until midnight for the tenant, not for the browser.
 */
export function endOfDayInDisplayZone(day: Date): Date {
  const nextMidnight = Date.UTC(day.getFullYear(), day.getMonth(), day.getDate() + 1)
  return new Date(wallClockToInstant(nextMidnight).getTime() - 1)
}

/**
 * The ISO-8601 week number (1-53) and the week-numbering year it belongs to,
 * based on the local calendar date parts (not UTC), so it matches the day as
 * shown in the UI. The year differs from the calendar year around New Year,
 * e.g. 2027-01-01 falls in week 53 of 2026.
 */
export function isoWeekAndYear(d: Date): { year: number; week: number } {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const day = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  return {
    year: date.getUTCFullYear(),
    week: Math.ceil(((date.getTime() - yearStart.getTime()) / DAY_MS + 1) / 7),
  }
}

/** The ISO-8601 week number (1-53) of a local `Date`, see `isoWeekAndYear`. */
export function getISOWeek(d: Date): number {
  return isoWeekAndYear(d).week
}

/**
 * Converts a Date to a YYYY-MM-DD string using local date parts, avoiding
 * the day shift that toISOString() introduces east of UTC, where a picked
 * local midnight is still the previous day in UTC.
 */
export function toDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** `toDateKey` for an optional date, passing null through. */
export function dateToParam(d: Date | null): string | null {
  return d ? toDateKey(d) : null
}

/**
 * Compact YYYY-MM-DD for a `planned_start`/`planned_end`/`actual_start`/
 * `actual_end`/`not_before` field in the production detail views, via
 * `dateToParam` rather than `formatISODate`, these are technical
 * scheduling fields, deliberately not subject to the display-format
 * preference. Empty placeholder for null.
 */
export function formatPlanned(iso: string | null): string {
  return iso
    ? (dateToParam(parseBackendTimestamp(iso)) ?? getEmptyPlaceholder())
    : getEmptyPlaceholder()
}
