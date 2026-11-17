import { parseBackendTimestamp } from '@/core/utils/dates'

/**
 * Durations given in whole seconds, rendered as hours and minutes the way
 * time tracking systems show worked time and balances: "7:42" for a
 * duration and "+7:42" or "-0:15" for a balance. Hours are not wrapped at
 * 24, so a month total reads "162:30". Seconds are dropped towards zero,
 * the same minute truncation the time tracking system applies, which also
 * keeps a balance of a few seconds from showing as "-0:00".
 */

function hoursAndMinutes(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}:${String(minutes).padStart(2, '0')}`
}

function wholeMinutes(seconds: number): number {
  return Math.trunc(Math.abs(seconds) / 60)
}

/** "7:42"; a negative value gets a leading minus, a positive one no sign. */
export function formatDuration(seconds: number): string {
  const minutes = wholeMinutes(seconds)
  const text = hoursAndMinutes(minutes)
  return seconds < 0 && minutes > 0 ? `-${text}` : text
}

/** "+7:42" or "-0:15"; zero has no sign. */
export function formatSignedDuration(seconds: number): string {
  const minutes = wholeMinutes(seconds)
  if (minutes === 0) return hoursAndMinutes(0)
  return `${seconds < 0 ? '-' : '+'}${hoursAndMinutes(minutes)}`
}

/**
 * The time between two backend timestamps as "3m 12s", or "45s" under a
 * minute, for how long a run took.
 */
export function formatElapsed(startedAt: string, finishedAt: string): string {
  const ms = parseBackendTimestamp(finishedAt).getTime() - parseBackendTimestamp(startedAt).getTime()
  const totalSeconds = Math.max(0, Math.round(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`
}
