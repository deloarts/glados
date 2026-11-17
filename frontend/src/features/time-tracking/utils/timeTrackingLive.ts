import { parseBackendTimestamp } from '@/core/utils/dates'
import type {
  TimeTrackingDay,
  TimeTrackingMonthResponse,
  TimeTrackingToday,
  TimeTrackingTotals,
} from '../types/timeTrackingTypes'

const MINUTE_MS = 60_000

/**
 * How much worked time has accrued since the month was fetched, for a
 * "worked so far today" figure that keeps ticking without a refetch. The
 * server computed its figures at `fetchedAt` on minute-truncated times, so
 * the increase is the number of whole server minutes passed since then.
 * The server clock is estimated from the client clock plus the offset seen
 * when the response arrived, so a client clock that runs a few minutes off
 * does not make the figure jump. Never negative.
 */
export function liveDeltaSeconds(fetchedAt: string, receivedAtMs: number, nowMs: number): number {
  const fetchedAtMs = parseBackendTimestamp(fetchedAt).getTime()
  const serverNowMs = nowMs + (fetchedAtMs - receivedAtMs)
  const minutes = Math.floor(serverNowMs / MINUTE_MS) - Math.floor(fetchedAtMs / MINUTE_MS)
  return Math.max(0, minutes) * 60
}

export interface LiveMonthFigures {
  days: TimeTrackingDay[]
  totals: TimeTrackingTotals | null
  today: TimeTrackingToday | null
}

function plus(value: number | null, delta: number): number | null {
  return value === null ? null : value + delta
}

/**
 * The month as it stands now: while clocked in, today's worked time, both
 * balances and the month totals grow by `deltaSeconds`, and today's row in
 * the table shows the same live figures as the totals; otherwise nothing
 * changes. The target-reached time is absolute, so it stays as fetched.
 */
export function withLiveToday(
  month: TimeTrackingMonthResponse,
  deltaSeconds: number,
): LiveMonthFigures {
  const totals = month.totals
  const today = totals?.today ?? null
  if (!totals || !today || !today.clocked_in) {
    return { days: month.days, totals, today }
  }
  const delta = Math.max(0, deltaSeconds)
  const liveToday: TimeTrackingToday = {
    ...today,
    worked_seconds: today.worked_seconds + delta,
    day_balance_seconds: today.day_balance_seconds + delta,
    running_balance_seconds: plus(today.running_balance_seconds, delta),
  }
  return {
    today: liveToday,
    totals: {
      ...totals,
      today: liveToday,
      worked_seconds: totals.worked_seconds + delta,
      balance_seconds: totals.balance_seconds + delta,
    },
    days: month.days.map((day) =>
      day.date === today.date
        ? {
            ...day,
            worked_seconds: liveToday.worked_seconds,
            day_balance_seconds: liveToday.day_balance_seconds,
            running_balance_seconds: liveToday.running_balance_seconds,
          }
        : day,
    ),
  }
}
