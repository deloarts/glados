import { getCurrentInstance, onMounted, readonly, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { getDisplayTimezone, minutesSinceMidnight } from '@/core/utils/dates'
import { useMinuteTick } from './useMinuteTick'

/** Shown until the current time is known, and for an unknown timezone. */
export const CLOCK_BASE_ICON = 'mdi-clock-outline'

const HOUR_ICON_NAMES = [
  'twelve',
  'one',
  'two',
  'three',
  'four',
  'five',
  'six',
  'seven',
  'eight',
  'nine',
  'ten',
  'eleven',
] as const

export { minutesSinceMidnight } from '@/core/utils/dates'

/**
 * The MDI hour icon for a time of day. Each hour icon covers the hour from
 * half past the previous hour (exclusive) to half past its own hour
 * (inclusive), so 10:31 to 11:30 shows eleven and 23:31 to 00:30 shows
 * twelve.
 */
export function clockIconForMinutes(minutes: number): string {
  const hour = ((Math.ceil((minutes - 30) / 60) % 12) + 12) % 12
  return `mdi-clock-time-${HOUR_ICON_NAMES[hour] ?? 'twelve'}-outline`
}

/**
 * A clock icon class that follows the time of day in the user's display
 * timezone, the zone the date formatters use, so it agrees with every time
 * shown in the app. It updates on the minute boundary and when the tab
 * becomes visible again, and starts out as the plain clock icon.
 */
export function useClockIcon(): Readonly<Ref<string>> {
  const icon = ref(CLOCK_BASE_ICON)

  function update(): void {
    const minutes = minutesSinceMidnight(new Date(), getDisplayTimezone())
    icon.value = minutes === null ? CLOCK_BASE_ICON : clockIconForMinutes(minutes)
  }

  useMinuteTick(update)

  // A changed timezone preference repaints at once rather than at the next
  // minute; registered after mount so the first render stays the base icon.
  const watchTimezone = () => watch(() => getDisplayTimezone(), update)
  if (getCurrentInstance()) onMounted(watchTimezone)
  else watchTimezone()

  return readonly(icon)
}
