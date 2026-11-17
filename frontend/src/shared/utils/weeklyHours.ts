/**
 * A week of working hours as the API carries it: each weekday (0 is Monday)
 * holds working intervals, each a local start time ("HH:MM") and a length in
 * minutes. A day without intervals is closed. The editors change the first
 * interval of a day and keep any further ones as they are.
 */
export interface WorkInterval {
  start: string
  minutes: number
}

// Keyed by the weekday as the API's JSON object keys are, a number reads too.
export type WeeklyHours = Record<string, WorkInterval[]>

export const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const
export const DEFAULT_DAY_START = '08:00'
export const DEFAULT_DAY_MINUTES = 480
export const MINUTES_PER_DAY = 1440

export function defaultWeeklyHours(): WeeklyHours {
  return Object.fromEntries(
    WEEKDAYS.map((day) => [
      day,
      day < 5 ? [{ start: DEFAULT_DAY_START, minutes: DEFAULT_DAY_MINUTES }] : [],
    ]),
  )
}

/** A copy of `week` with every weekday present and its intervals copied. */
export function copyWeeklyHours(week: WeeklyHours): WeeklyHours {
  return Object.fromEntries(
    WEEKDAYS.map((day) => [day, (week[day] ?? []).map((interval) => ({ ...interval }))]),
  )
}

export function dayMinutes(intervals: WorkInterval[]): number {
  return intervals.reduce((sum, interval) => sum + interval.minutes, 0)
}
