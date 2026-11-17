import { describe, it, expect, afterEach } from 'vitest'

import { setDisplayDateFormat, setDisplayTimezone } from '@/core/utils/dates'
import { formatAccountValue } from '../accountValueFormat'
import { liveDeltaSeconds, withLiveToday } from '../timeTrackingLive'
import { dayLabel, monthKeyAt, shiftMonth, yearOfMonth } from '../timeTrackingMonth'
import { countedDays, formatMinutesOfDay, monthKpis, weekdayStats } from '../timeTrackingStats'
import type { TimeTrackingDay, TimeTrackingMonthResponse } from '../../types/timeTrackingTypes'

function day(date: string, overrides: Partial<TimeTrackingDay> = {}): TimeTrackingDay {
  return {
    date,
    weekday: new Date(`${date}T00:00:00Z`).getUTCDay() || 7,
    shift_name: null,
    shift_short_name: null,
    first_in: `${date}T07:00:00Z`,
    last_out: `${date}T15:30:00Z`,
    bookings: [],
    worked_seconds: 8 * 3600,
    target_seconds: 8 * 3600,
    day_balance_seconds: 0,
    running_balance_seconds: 0,
    status: 'normal',
    ...overrides,
  }
}

describe('liveDeltaSeconds', () => {
  const fetchedAt = '2026-10-06T08:30:20Z'
  const fetchedMs = Date.parse(fetchedAt)

  it('counts whole server minutes since the fetch', () => {
    expect(liveDeltaSeconds(fetchedAt, fetchedMs, fetchedMs + 39_000)).toBe(0)
    expect(liveDeltaSeconds(fetchedAt, fetchedMs, fetchedMs + 40_000)).toBe(60)
    expect(liveDeltaSeconds(fetchedAt, fetchedMs, fetchedMs + 160_000)).toBe(180)
  })

  it('follows the server clock, not a skewed client clock', () => {
    // The client clock runs five minutes behind the server.
    const receivedAt = fetchedMs - 5 * 60_000
    expect(liveDeltaSeconds(fetchedAt, receivedAt, receivedAt + 40_000)).toBe(60)
  })

  it('never goes negative', () => {
    expect(liveDeltaSeconds(fetchedAt, fetchedMs, fetchedMs - 120_000)).toBe(0)
  })
})

describe('withLiveToday', () => {
  function month(clockedIn: boolean): TimeTrackingMonthResponse {
    return {
      month: '2026-10',
      first_day: '2026-10-01',
      last_day: '2026-10-31',
      employee_name: 'Doe, Jane',
      days: [day('2026-10-05'), day('2026-10-06', { worked_seconds: 3600, running_balance_seconds: null })],
      accounts: [],
      totals: {
        today: {
          date: '2026-10-06',
          worked_seconds: 3600,
          target_seconds: 8 * 3600,
          day_balance_seconds: -7 * 3600,
          running_balance_seconds: -7 * 3600,
          clocked_in: clockedIn,
          first_in: '2026-10-06T07:00:00Z',
          target_reached_at: '2026-10-06T15:00:00Z',
        },
        worked_seconds: 9 * 3600,
        target_seconds: 16 * 3600,
        balance_seconds: -7 * 3600,
      },
      rights: { days: null, month: true, year: null },
      fetched_at: '2026-10-06T08:00:00Z',
    }
  }

  it('advances today, its row and the month totals while clocked in', () => {
    const live = withLiveToday(month(true), 120)

    expect(live.today?.worked_seconds).toBe(3600 + 120)
    expect(live.today?.day_balance_seconds).toBe(-7 * 3600 + 120)
    expect(live.today?.running_balance_seconds).toBe(-7 * 3600 + 120)
    expect(live.today?.target_reached_at).toBe('2026-10-06T15:00:00Z')
    expect(live.totals?.worked_seconds).toBe(9 * 3600 + 120)
    expect(live.totals?.balance_seconds).toBe(-7 * 3600 + 120)
    expect(live.days[1]?.worked_seconds).toBe(3600 + 120)
    expect(live.days[1]?.running_balance_seconds).toBe(-7 * 3600 + 120)
    expect(live.days[0]?.worked_seconds).toBe(8 * 3600)
  })

  it('leaves everything as fetched while clocked out', () => {
    const fetched = month(false)
    const live = withLiveToday(fetched, 120)

    expect(live.totals).toBe(fetched.totals)
    expect(live.days).toBe(fetched.days)
  })
})

describe('month keys', () => {
  afterEach(() => setDisplayTimezone(null))

  it('takes the month in the given timezone', () => {
    const lateEvening = new Date('2026-10-31T23:30:00Z')
    expect(monthKeyAt(lateEvening, 'UTC')).toBe('2026-10')
    expect(monthKeyAt(lateEvening, 'Europe/Vienna')).toBe('2026-11')
  })

  it('steps across year boundaries', () => {
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2025-12', 1)).toBe('2026-01')
    expect(shiftMonth('2026-10', -10)).toBe('2025-12')
    expect(yearOfMonth('2025-12')).toBe(2025)
  })
})

describe('dayLabel', () => {
  afterEach(() => setDisplayDateFormat(null))

  it('writes the weekday and the date in the user\'s date format', () => {
    setDisplayDateFormat('dmy_dot')
    expect(dayLabel('2026-10-05')).toBe('Monday, 05.10.2026')
    setDisplayDateFormat('iso')
    expect(dayLabel('2026-10-04')).toBe('Sunday, 2026-10-04')
  })
})

describe('statistics', () => {
  afterEach(() => setDisplayTimezone(null))

  const days = [
    day('2026-10-05', { worked_seconds: 9 * 3600, day_balance_seconds: 3600 }),
    day('2026-10-06', { worked_seconds: 7 * 3600, day_balance_seconds: -3600 }),
    day('2026-10-12', { worked_seconds: 8 * 3600, first_in: '2026-10-12T08:00:00Z' }),
    day('2026-10-11', { worked_seconds: null }),
    day('2026-10-13', { worked_seconds: 2 * 3600 }),
  ]

  it('counts days with worked time and leaves the running day out', () => {
    expect(countedDays(days, '2026-10-13').map((d) => d.date)).toEqual([
      '2026-10-05',
      '2026-10-06',
      '2026-10-12',
    ])
  })

  it('computes days worked, the average and longest day and overtime days', () => {
    const kpis = monthKpis(countedDays(days, '2026-10-13'))

    expect(kpis.daysWorked).toBe(3)
    expect(kpis.averageDaySeconds).toBe(8 * 3600)
    expect(kpis.longestDay).toEqual({ date: '2026-10-05', seconds: 9 * 3600 })
    expect(kpis.overtimeDays).toBe(1)
  })

  it('averages worked time and first in per weekday in the display timezone', () => {
    setDisplayTimezone('Europe/Vienna')
    const monday = weekdayStats(countedDays(days, '2026-10-13')).find((row) => row.weekday === 1)!

    expect(monday.days).toBe(2)
    expect(monday.averageWorkedSeconds).toBe(8.5 * 3600)
    // 07:00 and 08:00 UTC are 09:00 and 10:00 in Vienna in October.
    expect(formatMinutesOfDay(monday.averageFirstInMinutes!)).toBe('09:30')
  })
})

describe('formatAccountValue', () => {
  it('writes each value by its format', () => {
    expect(formatAccountValue(7 * 3600 + 30 * 60, 'duration_clock')).toBe('7:30')
    expect(formatAccountValue(-(15 * 60), 'duration_clock')).toBe('-0:15')
    expect(formatAccountValue(5400, 'duration_hours')).toBe('1.50')
    expect(formatAccountValue(12.4, 'count')).toBe('12')
    expect(formatAccountValue(2.5, 'decimal')).toBe('2.50')
    expect(formatAccountValue(42.5, 'raw')).toBe('42.5')
  })

  it('writes currency in cents with the display currency', () => {
    expect(formatAccountValue(1250, 'money')).toBe('€12.50')
  })
})
