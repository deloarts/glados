import { describe, it, expect, beforeEach } from 'vitest'

import { TEST_SUBJECT_KEY, monthKeyOf, rollTestSubject, testSubjectName } from '../testSubject'

/** Always wins the roll / always loses it. */
const always = () => 0
const never = () => 1

describe('monthKeyOf', () => {
  it('is stable across a month and changes at the boundary', () => {
    expect(monthKeyOf(new Date(2026, 7, 1))).toBe('2026-08')
    expect(monthKeyOf(new Date(2026, 7, 31, 23, 59))).toBe('2026-08')
    expect(monthKeyOf(new Date(2026, 8, 1, 0, 1))).toBe('2026-09')
  })

  it('pads single-digit months', () => {
    expect(monthKeyOf(new Date(2026, 0, 15))).toBe('2026-01')
  })
})

describe('testSubjectName', () => {
  it('uses the database id', () => {
    expect(testSubjectName(42)).toBe('Test subject #42')
  })
})

describe('rollTestSubject', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('reveals and records the month when the roll wins', () => {
    expect(rollTestSubject(new Date(2026, 7, 10), always)).toBe(true)
    expect(localStorage.getItem(TEST_SUBJECT_KEY)).toBe('2026-08')
  })

  it('never reveals twice in the same month', () => {
    expect(rollTestSubject(new Date(2026, 7, 10), always)).toBe(true)
    expect(rollTestSubject(new Date(2026, 7, 11), always)).toBe(false)
    expect(rollTestSubject(new Date(2026, 7, 31), always)).toBe(false)
  })

  it('re-arms in the next month', () => {
    rollTestSubject(new Date(2026, 7, 10), always)

    expect(rollTestSubject(new Date(2026, 8, 1), always)).toBe(true)
    expect(localStorage.getItem(TEST_SUBJECT_KEY)).toBe('2026-09')
  })

  // Burning the allowance on a losing roll would mean most months never reveal
  // at all: the cap is on reveals, not on attempts.
  it('does not spend the month on a losing roll', () => {
    expect(rollTestSubject(new Date(2026, 7, 10), never)).toBe(false)
    expect(localStorage.getItem(TEST_SUBJECT_KEY)).toBeNull()

    expect(rollTestSubject(new Date(2026, 7, 10), always)).toBe(true)
  })
})
