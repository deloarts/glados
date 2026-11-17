import { getDisplayTimezone, minutesSinceMidnight, parseBackendTimestamp } from '@/core/utils/dates'
import type { TimeTrackingDay } from '../types/timeTrackingTypes'

/**
 * Statistics derived from one month's days for the Time Tracking view.
 * They count days with worked time up to today; a day that is still
 * running (today while clocked in) is left out, since its partial figure
 * would pull every average down. Times of day are read in the user's
 * display timezone.
 */

export interface WeekdayStat {
  /** ISO weekday, 1 is Monday. */
  weekday: number
  days: number
  averageWorkedSeconds: number | null
  averageFirstInMinutes: number | null
  averageLastOutMinutes: number | null
}

export interface MonthKpis {
  daysWorked: number
  averageDaySeconds: number | null
  longestDay: { date: string; seconds: number } | null
  overtimeDays: number
}

/** The days the statistics count. `runningDate` is today while clocked in. */
export function countedDays(days: TimeTrackingDay[], runningDate: string | null): TimeTrackingDay[] {
  return days.filter(
    (day) => day.date !== runningDate && day.worked_seconds !== null && day.worked_seconds > 0,
  )
}

function average(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function minutesOf(iso: string | null): number | null {
  if (!iso) return null
  return minutesSinceMidnight(parseBackendTimestamp(iso), getDisplayTimezone())
}

function firstInOf(day: TimeTrackingDay): string | null {
  return day.first_in ?? day.bookings.find((booking) => booking.direction === 'in')?.at ?? null
}

function lastOutOf(day: TimeTrackingDay): string | null {
  if (day.last_out) return day.last_out
  const outs = day.bookings.filter((booking) => booking.direction === 'out')
  return outs[outs.length - 1]?.at ?? null
}

export function weekdayStats(days: TimeTrackingDay[]): WeekdayStat[] {
  return [1, 2, 3, 4, 5, 6, 7].map((weekday) => {
    const matching = days.filter((day) => day.weekday === weekday)
    const firstIns = matching.map((day) => minutesOf(firstInOf(day))).filter((m) => m !== null)
    const lastOuts = matching.map((day) => minutesOf(lastOutOf(day))).filter((m) => m !== null)
    return {
      weekday,
      days: matching.length,
      averageWorkedSeconds: average(matching.map((day) => day.worked_seconds ?? 0)),
      averageFirstInMinutes: average(firstIns),
      averageLastOutMinutes: average(lastOuts),
    }
  })
}

/** Average first-in and last-out over all counted days. */
export function averageDayBounds(days: TimeTrackingDay[]): {
  firstInMinutes: number | null
  lastOutMinutes: number | null
} {
  return {
    firstInMinutes: average(
      days.map((day) => minutesOf(firstInOf(day))).filter((m) => m !== null),
    ),
    lastOutMinutes: average(
      days.map((day) => minutesOf(lastOutOf(day))).filter((m) => m !== null),
    ),
  }
}

export function monthKpis(days: TimeTrackingDay[]): MonthKpis {
  let longestDay: MonthKpis['longestDay'] = null
  for (const day of days) {
    const seconds = day.worked_seconds ?? 0
    if (!longestDay || seconds > longestDay.seconds) longestDay = { date: day.date, seconds }
  }
  return {
    daysWorked: days.length,
    averageDaySeconds: average(days.map((day) => day.worked_seconds ?? 0)),
    longestDay,
    overtimeDays: days.filter((day) => (day.day_balance_seconds ?? 0) > 0).length,
  }
}

/** "07:42" for minutes since midnight, rounded to the minute. */
export function formatMinutesOfDay(minutes: number): string {
  const rounded = Math.round(minutes)
  const hours = Math.floor(rounded / 60) % 24
  return `${String(hours).padStart(2, '0')}:${String(rounded % 60).padStart(2, '0')}`
}
