import type { MachineCapacityDayResponse } from '../types/scheduleBoardResponse'

export function utilizationClass(day: MachineCapacityDayResponse | undefined): string {
  if (!day || day.available_minutes === 0) return ''
  const ratio = day.booked_minutes / day.available_minutes
  if (ratio > 1) return 'utilization-over'
  if (ratio >= 0.7) return 'utilization-high'
  return 'utilization-normal'
}

// The fallback covers days without a capacity row.
export function overbookedMinutes(day: MachineCapacityDayResponse | undefined): number {
  return day?.overbooked_minutes ?? 0
}
