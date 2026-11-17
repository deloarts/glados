import { describe, it, expect } from 'vitest'

import { pickDailyMessage } from '../dailyGreeting'

describe('pickDailyMessage', () => {
  it('returns an empty string for an empty message pool', () => {
    expect(pickDailyMessage([], new Date('2026-01-01T12:00:00'))).toBe('')
  })

  it('is deterministic for the same local calendar day', () => {
    const messages = ['a', 'b', 'c', 'd']
    const morning = new Date('2026-01-05T06:00:00')
    const evening = new Date('2026-01-05T23:59:00')

    expect(pickDailyMessage(messages, morning)).toBe(pickDailyMessage(messages, evening))
  })

  it('picks a message within the pool bounds regardless of the date', () => {
    const messages = ['a', 'b', 'c']
    const result = pickDailyMessage(messages, new Date('2026-03-17T10:00:00'))
    expect(messages).toContain(result)
  })

  it('rotates to a different entry across different calendar days (pool larger than 1)', () => {
    const messages = ['a', 'b']
    const day1 = pickDailyMessage(messages, new Date('2026-01-01T12:00:00'))
    const day2 = pickDailyMessage(messages, new Date('2026-01-02T12:00:00'))
    // Consecutive days advance the index by exactly one, so with a 2-entry
    // pool they can never land on the same message.
    expect(day1).not.toBe(day2)
  })

  it('wraps back to the start once the day index exceeds the pool length', () => {
    const messages = ['only-one']
    expect(pickDailyMessage(messages, new Date('2026-01-01T00:00:00'))).toBe('only-one')
    expect(pickDailyMessage(messages, new Date('2099-12-31T23:59:59'))).toBe('only-one')
  })
})
