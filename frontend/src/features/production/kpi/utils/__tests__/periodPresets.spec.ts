import { describe, it, expect } from 'vitest'

import { previousPeriodOf, resolvePeriodPreset } from '../periodPresets'

// A fixed Wednesday, so week/month boundaries are unambiguous regardless of
// when this suite runs.
const REFERENCE = new Date(2026, 8, 23) // 2026-09-23, a Wednesday

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

describe('resolvePeriodPreset', () => {
  it('this_week resolves to the Monday-Sunday week containing now', () => {
    const [from, to] = resolvePeriodPreset('this_week', REFERENCE)
    expect(ymd(from)).toBe('2026-09-21')
    expect(ymd(to)).toBe('2026-09-27')
  })

  it('last_week is the immediately preceding Monday-Sunday week', () => {
    const [from, to] = resolvePeriodPreset('last_week', REFERENCE)
    expect(ymd(from)).toBe('2026-09-14')
    expect(ymd(to)).toBe('2026-09-20')
  })

  it('this_month resolves to the full calendar month containing now', () => {
    const [from, to] = resolvePeriodPreset('this_month', REFERENCE)
    expect(ymd(from)).toBe('2026-09-01')
    expect(ymd(to)).toBe('2026-09-30')
  })

  it('last_month resolves to the full preceding calendar month', () => {
    const [from, to] = resolvePeriodPreset('last_month', REFERENCE)
    expect(ymd(from)).toBe('2026-08-01')
    expect(ymd(to)).toBe('2026-08-31')
  })

  it('last_month rolls back across a year boundary', () => {
    const january = new Date(2026, 0, 15)
    const [from, to] = resolvePeriodPreset('last_month', january)
    expect(ymd(from)).toBe('2025-12-01')
    expect(ymd(to)).toBe('2025-12-31')
  })

  it('last_90_days is a 90-day trailing window ending today, inclusive', () => {
    const [from, to] = resolvePeriodPreset('last_90_days', REFERENCE)
    expect(ymd(to)).toBe('2026-09-23')
    expect(ymd(from)).toBe('2026-06-26')
    const spanDays = Math.round((to.getTime() - from.getTime()) / 86400000) + 1
    expect(spanDays).toBe(90)
  })
})

describe('previousPeriodOf', () => {
  it('shifts a 7-day period back by exactly 7 days, non-overlapping', () => {
    const from = new Date(2026, 8, 21)
    const to = new Date(2026, 8, 27)
    const [prevFrom, prevTo] = previousPeriodOf(from, to)
    expect(ymd(prevFrom)).toBe('2026-09-14')
    expect(ymd(prevTo)).toBe('2026-09-20')
  })

  it('preserves the length of an arbitrary custom range', () => {
    const from = new Date(2026, 0, 10)
    const to = new Date(2026, 0, 14) // 5-day range
    const [prevFrom, prevTo] = previousPeriodOf(from, to)
    expect(ymd(prevFrom)).toBe('2026-01-05')
    expect(ymd(prevTo)).toBe('2026-01-09')
  })

  it('handles a single-day period', () => {
    const from = new Date(2026, 8, 23)
    const to = new Date(2026, 8, 23)
    const [prevFrom, prevTo] = previousPeriodOf(from, to)
    expect(ymd(prevFrom)).toBe('2026-09-22')
    expect(ymd(prevTo)).toBe('2026-09-22')
  })

  it('rolls back across a month boundary', () => {
    const from = new Date(2026, 8, 1)
    const to = new Date(2026, 8, 5)
    const [prevFrom, prevTo] = previousPeriodOf(from, to)
    expect(ymd(prevFrom)).toBe('2026-08-27')
    expect(ymd(prevTo)).toBe('2026-08-31')
  })
})
