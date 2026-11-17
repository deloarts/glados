import { formatISODate, formatISODateTime, formatISOTime, toDayKey } from '@/core/utils/dates'

/** A meeting's date with its start and end time, or both instants when it spans days. */
export function formatMeetingWhen(startsAt: string, endsAt: string): string {
  if (toDayKey(startsAt) === toDayKey(endsAt)) {
    return `${formatISODate(startsAt)}, ${formatISOTime(startsAt)} – ${formatISOTime(endsAt)}`
  }
  return `${formatISODateTime(startsAt)} – ${formatISODateTime(endsAt)}`
}

/** The start and end time of a meeting on its day, for the second line of a date cell. */
export function formatMeetingTimes(startsAt: string, endsAt: string): string {
  return `${formatISOTime(startsAt)} – ${formatISOTime(endsAt)}`
}

/** The next meeting as agreed: its date, its wall-clock time if set. */
export function formatNextMeeting(date: string | null, time: string | null): string | null {
  if (!date) return null
  return time ? `${formatISODate(date)}, ${time.slice(0, 5)}` : formatISODate(date)
}
