import { webApi } from '@/core/api/webRequest'
import type { WeeklyHours } from '@/shared/utils/weeklyHours'

/**
 * The default calendar: the weekly hours of every machine without its own
 * override, and of manual work. Saving it needs the right to edit machines.
 */
export async function getDefaultWorkingHours(): Promise<WeeklyHours> {
  return webApi.get('/production-machines/default-working-hours')
}

export async function setDefaultWorkingHours(weeklyHours: WeeklyHours): Promise<WeeklyHours> {
  return webApi.put('/production-machines/default-working-hours', {
    body: { weekly_hours: weeklyHours },
  })
}
