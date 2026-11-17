import { formatISODate, localeTag, weekdayName, zonedParts } from '@/core/utils/dates'

/**
 * Month keys ("YYYY-MM", the format the month route takes) and the labels
 * the Time Tracking view shows for them. "Now" is read in the user's
 * display timezone, the same zone every time on the page is shown in, so
 * the current month and the highlighted day agree with the clock.
 */

/** The month `date` falls in on the wall clock of `timeZone`. */
export function monthKeyAt(date: Date, timeZone: string): string {
  try {
    const { year, month } = zonedParts(date, timeZone)
    if (year && month) return `${year}-${month}`
  } catch {
    // An unknown zone falls back to the browser's own below.
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

function parse(key: string): { year: number; month: number } {
  const [year, month] = key.split('-').map(Number)
  return { year: year ?? 1970, month: month ?? 1 }
}

/** The month `delta` months after `key` (negative goes back). */
export function shiftMonth(key: string, delta: number): string {
  const { year, month } = parse(key)
  const index = year * 12 + (month - 1) + delta
  const nextYear = Math.floor(index / 12)
  const nextMonth = (index % 12) + 1
  return `${nextYear}-${String(nextMonth).padStart(2, '0')}`
}

export function yearOfMonth(key: string): number {
  return parse(key).year
}

/** "October 2026" in the UI language. */
export function monthLabel(key: string): string {
  const { year, month } = parse(key)
  return new Intl.DateTimeFormat(localeTag(), {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(Date.UTC(year, month - 1, 1))
}

/** Short weekday name of ISO weekday `weekday` (1 is Monday). */
export function shortWeekdayName(weekday: number): string {
  // 2024-01-01 was a Monday.
  return weekdayName(new Date(2024, 0, weekday))
}

/**
 * A day as "Monday, 05.10.2026": the weekday in the UI language and the date
 * in the user's date format preference.
 */
export function dayLabel(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  const weekday = weekdayName(new Date(year!, month! - 1, day!), 'long')
  return `${weekday}, ${formatISODate(isoDate.slice(0, 10))}`
}
