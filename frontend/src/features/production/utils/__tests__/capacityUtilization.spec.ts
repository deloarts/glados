import { describe, it, expect } from 'vitest'

import { overbookedMinutes, utilizationClass } from '../capacityUtilization'

import type { MachineCapacityDayResponse } from '../../types/scheduleBoardResponse'

function day(overrides: Partial<MachineCapacityDayResponse> = {}): MachineCapacityDayResponse {
  return {
    date: '2026-08-27',
    booked_minutes: 0,
    available_minutes: 480,
    overbooked_minutes: 0,
    ...overrides,
  }
}

describe('utilizationClass', () => {
  it('returns empty string for undefined (no capacity data for that day)', () => {
    expect(utilizationClass(undefined)).toBe('')
  })

  it('returns empty string when available_minutes is 0 (avoids a divide-by-zero ratio)', () => {
    expect(utilizationClass(day({ booked_minutes: 30, available_minutes: 0 }))).toBe('')
  })

  it('returns utilization-over when booked exceeds available', () => {
    expect(utilizationClass(day({ booked_minutes: 500, available_minutes: 480 }))).toBe(
      'utilization-over',
    )
  })

  it('returns utilization-high at 70% or more but not over', () => {
    expect(utilizationClass(day({ booked_minutes: 336, available_minutes: 480 }))).toBe(
      'utilization-high',
    )
  })

  it('returns utilization-normal below 70%', () => {
    expect(utilizationClass(day({ booked_minutes: 100, available_minutes: 480 }))).toBe(
      'utilization-normal',
    )
  })
})

describe('overbookedMinutes', () => {
  it('is 0 for undefined', () => {
    expect(overbookedMinutes(undefined)).toBe(0)
  })

  it('is 0 when nothing is overbooked', () => {
    expect(overbookedMinutes(day())).toBe(0)
  })

  it('passes through a positive overbooked_minutes value', () => {
    expect(overbookedMinutes(day({ overbooked_minutes: 90 }))).toBe(90)
  })
})
