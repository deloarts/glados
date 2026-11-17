/**
 * When the cake is allowed to appear: once a week, at a random hour-long
 * window, on a random weekday, somewhere between 09:00 and 14:00 local time.
 *
 * The window is rolled once per week and persisted, so it is stable across
 * reloads and across tabs in the same browser. Otherwise every refresh would
 * be another roll of the dice and the cake would show up constantly.
 */

/** Earliest the window may open (09:00, in minutes past midnight). */
const EARLIEST_START_MIN = 9 * 60
/** Latest the window may close (14:00). The whole window fits inside this. */
const LATEST_END_MIN = 14 * 60
/** "About an hour". */
const MIN_DURATION_MIN = 50
const MAX_DURATION_MIN = 70

export interface CakeWindow {
  /**
   * Monday of the week this was rolled for, `YYYY-MM-DD`, used to know when
   * to reroll.
   */
  weekKey: string
  /** Epoch ms the cake appears, or null when the week had no slot left. */
  startsAt: number | null
  durationMs: number
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function toDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/**
 * Local-time Monday of `date`'s week, as `YYYY-MM-DD`. Used instead of an ISO
 * week number purely to sidestep the year-boundary edge cases. It identifies a
 * week just as uniquely.
 */
export function weekKeyOf(date: Date): string {
  const monday = new Date(date)
  // getDay() is 0 for Sunday, which belongs to the week that started six days
  // earlier rather than the one starting tomorrow.
  const offset = (monday.getDay() + 6) % 7
  monday.setDate(monday.getDate() - offset)
  monday.setHours(0, 0, 0, 0)
  return toDateKey(monday)
}

/**
 * Integer in `[min, max]`. Clamped rather than trusting `random()` to stay
 * below 1, because the inclusive `+1` overshoots by one at exactly 1.0, and this is
 * used for the window's end time, which must never cross 14:00.
 */
function randomInt(min: number, max: number, random: () => number): number {
  if (max <= min) return min
  return Math.min(max, min + Math.floor(random() * (max - min + 1)))
}

function atMinutes(day: Date, minutes: number): Date {
  const result = new Date(day)
  result.setHours(0, minutes, 0, 0)
  return result
}

/**
 * Rolls this week's window.
 *
 * Only ever picks a slot that is still in the future, and only on the weekdays
 * left in the current week, so rolling on a Thursday afternoon can still land
 * on Friday, and rolling late on a Friday correctly yields "no cake this week"
 * rather than a window that already passed.
 *
 * `random` is injectable so tests can pin the outcome.
 */
export function rollCakeWindow(now: Date, random: () => number = Math.random): CakeWindow {
  const weekKey = weekKeyOf(now)
  const durationMin = randomInt(MIN_DURATION_MIN, MAX_DURATION_MIN, random)
  const latestStartMin = LATEST_END_MIN - durationMin

  const nowMinutes = now.getHours() * 60 + now.getMinutes()

  // Candidate weekdays: today through Sunday, Monday-Friday only.
  const candidates: { day: Date; earliest: number }[] = []
  for (let offset = 0; offset < 7; offset++) {
    const day = new Date(now)
    day.setDate(day.getDate() + offset)
    if (weekKeyOf(day) !== weekKey) break

    const weekday = day.getDay()
    if (weekday === 0 || weekday === 6) continue

    const earliest =
      offset === 0 ? Math.max(EARLIEST_START_MIN, nowMinutes + 1) : EARLIEST_START_MIN
    if (earliest > latestStartMin) continue

    candidates.push({ day, earliest })
  }

  if (candidates.length === 0) {
    return { weekKey, startsAt: null, durationMs: durationMin * 60_000 }
  }

  const picked = candidates[randomInt(0, candidates.length - 1, random)]!
  const startMin = randomInt(picked.earliest, latestStartMin, random)

  return {
    weekKey,
    startsAt: atMinutes(picked.day, startMin).getTime(),
    durationMs: durationMin * 60_000,
  }
}

export function isCakeWindowOpen(window: CakeWindow | null, now: Date): boolean {
  if (!window?.startsAt) return false
  const time = now.getTime()
  return time >= window.startsAt && time < window.startsAt + window.durationMs
}

/** True once the stored window is for a week that has passed. */
export function isCakeWindowStale(window: CakeWindow | null, now: Date): boolean {
  return !window || window.weekKey !== weekKeyOf(now)
}
