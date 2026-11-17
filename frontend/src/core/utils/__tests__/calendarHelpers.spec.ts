import { describe, it, expect } from 'vitest'

import {
  DAY_MS,
  addDays,
  earlierDate,
  endOfWeek,
  formatTimeInZone,
  getISOWeek,
  isoWeekAndYear,
  localeTag,
  minutesSinceMidnight,
  monthName,
  startOfDay,
  startOfWeek,
  weekdayName,
  zonedParts,
} from '@/core/utils/dates'

describe('DAY_MS', () => {
  it('is one 24-hour day in milliseconds', () => {
    expect(DAY_MS).toBe(86_400_000)
  })
})

describe('startOfDay', () => {
  it('returns a copy at local midnight', () => {
    const input = new Date(2026, 7, 6, 14, 32, 11, 500)
    const result = startOfDay(input)
    expect(result).toEqual(new Date(2026, 7, 6))
    expect(input.getHours()).toBe(14)
  })
})

describe('addDays', () => {
  it('moves by calendar days and keeps the time of day', () => {
    expect(addDays(new Date(2026, 7, 30, 9, 15), 3)).toEqual(new Date(2026, 8, 2, 9, 15))
    expect(addDays(new Date(2026, 0, 1), -1)).toEqual(new Date(2025, 11, 31))
  })

  it('leaves the input untouched', () => {
    const input = new Date(2026, 7, 6)
    addDays(input, 5)
    expect(input).toEqual(new Date(2026, 7, 6))
  })
})

describe('startOfWeek', () => {
  it('returns local midnight on the Monday of the week', () => {
    // 2026-08-06 is a Thursday, 2026-08-09 a Sunday.
    expect(startOfWeek(new Date(2026, 7, 6, 18))).toEqual(new Date(2026, 7, 3))
    expect(startOfWeek(new Date(2026, 7, 9, 23, 59))).toEqual(new Date(2026, 7, 3))
    expect(startOfWeek(new Date(2026, 7, 3, 8))).toEqual(new Date(2026, 7, 3))
  })
})

describe('endOfWeek', () => {
  it('returns local midnight on the Sunday that ends the week', () => {
    // 2026-08-03 is a Monday, 2026-08-09 a Sunday.
    expect(endOfWeek(new Date(2026, 7, 3, 8))).toEqual(new Date(2026, 7, 9))
    expect(endOfWeek(new Date(2026, 7, 6, 18))).toEqual(new Date(2026, 7, 9))
    expect(endOfWeek(new Date(2026, 7, 9, 23, 59))).toEqual(new Date(2026, 7, 9))
  })
})

describe('earlierDate', () => {
  const a = new Date(2026, 7, 6)
  const b = new Date(2026, 7, 9)

  it('picks the earlier date and treats null as no constraint', () => {
    expect(earlierDate(a, b)).toBe(a)
    expect(earlierDate(b, a)).toBe(a)
    expect(earlierDate(null, b)).toBe(b)
    expect(earlierDate(a, null)).toBe(a)
    expect(earlierDate(null, null)).toBeNull()
  })
})

describe('isoWeekAndYear', () => {
  it('returns the week and its week-numbering year', () => {
    expect(isoWeekAndYear(new Date(2026, 7, 6))).toEqual({ year: 2026, week: 32 })
    // 2027-01-01 is a Friday, still in the last week of 2026.
    expect(isoWeekAndYear(new Date(2027, 0, 1))).toEqual({ year: 2026, week: 53 })
    // 2024-12-30 is a Monday, already in week 1 of 2025.
    expect(isoWeekAndYear(new Date(2024, 11, 30))).toEqual({ year: 2025, week: 1 })
  })

  it('agrees with getISOWeek', () => {
    const date = new Date(2027, 0, 1)
    expect(getISOWeek(date)).toBe(isoWeekAndYear(date).week)
  })
})

describe('zonedParts', () => {
  const instant = new Date('2026-10-31T23:30:00Z')

  it('reads the wall clock of the given zone', () => {
    expect(zonedParts(instant, 'UTC')).toEqual({
      year: '2026',
      month: '10',
      day: '31',
      hour: '23',
      minute: '30',
    })
    expect(zonedParts(instant, 'Europe/Vienna')).toEqual({
      year: '2026',
      month: '11',
      day: '01',
      hour: '00',
      minute: '30',
    })
  })

  it('throws for an unknown zone', () => {
    expect(() => zonedParts(instant, 'Not/AZone')).toThrow(RangeError)
  })
})

describe('minutesSinceMidnight', () => {
  it('counts minutes on the wall clock of the zone', () => {
    const instant = new Date('2026-08-06T12:05:00Z')
    expect(minutesSinceMidnight(instant, 'UTC')).toBe(12 * 60 + 5)
    expect(minutesSinceMidnight(instant, 'Europe/Vienna')).toBe(14 * 60 + 5)
  })

  it('is null for an unknown zone', () => {
    expect(minutesSinceMidnight(new Date(), 'Not/AZone')).toBeNull()
  })
})

describe('formatTimeInZone', () => {
  it('renders a 24-hour time in the zone', () => {
    const instant = new Date('2026-08-06T14:32:00Z')
    expect(formatTimeInZone(instant, 'UTC')).toBe('14:32')
    expect(formatTimeInZone(instant, 'Europe/Vienna')).toBe('16:32')
  })
})

describe('monthName / weekdayName', () => {
  it('names a month number in the UI language', () => {
    const expected = (month: number, style: 'long' | 'short') =>
      new Intl.DateTimeFormat(localeTag(), { month: style, timeZone: 'UTC' }).format(
        Date.UTC(2026, month - 1, 1),
      )
    expect(monthName(1)).toBe(expected(1, 'short'))
    expect(monthName(12, 'long')).toBe(expected(12, 'long'))
  })

  it('names the weekday of a local date in the UI language', () => {
    const thursday = new Date(2026, 7, 6)
    expect(weekdayName(thursday)).toBe(
      thursday.toLocaleDateString(localeTag(), { weekday: 'short' }),
    )
    expect(weekdayName(thursday, 'long')).toBe(
      thursday.toLocaleDateString(localeTag(), { weekday: 'long' }),
    )
  })
})
