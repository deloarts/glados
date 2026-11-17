import { DAY_MS } from '@/core/utils/dates'

// Picks an entry deterministically by local calendar day, so it is stable
// all day and rotates at midnight.
export function pickDailyMessage(messages: string[], date: Date = new Date()): string {
  if (messages.length === 0) return ''
  const localMidnightUtcMs = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
  const dayIndex = Math.floor(localMidnightUtcMs / DAY_MS)
  return messages[((dayIndex % messages.length) + messages.length) % messages.length] ?? ''
}
