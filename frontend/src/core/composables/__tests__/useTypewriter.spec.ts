import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import { useTypewriter } from '../useTypewriter'

// jitterRatio 0 throughout: the schedule has to be exact for fake timers to
// land on known states.
const OPTIONS = { phrase: 'abc', maxRows: 2, charDelayMs: 10, rowDelayMs: 20, jitterRatio: 0 }

describe('useTypewriter', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('types one character at a time', () => {
    const writer = useTypewriter(OPTIONS)
    writer.start()

    expect(writer.current.value).toBe('')
    vi.advanceTimersByTime(10)
    expect(writer.current.value).toBe('a')
    vi.advanceTimersByTime(20)
    expect(writer.current.value).toBe('abc')
  })

  it('completes rows in order and stops at maxRows', () => {
    const writer = useTypewriter(OPTIONS)
    writer.start()

    vi.advanceTimersByTime(1000)

    expect(writer.rows.value).toEqual(['abc', 'abc'])
    expect(writer.current.value).toBe('')
    expect(writer.isDone.value).toBe(true)
  })

  it('stops cleanly mid-row and schedules nothing further', () => {
    const writer = useTypewriter(OPTIONS)
    writer.start()
    vi.advanceTimersByTime(10)
    writer.stop()

    const frozen = writer.current.value
    vi.advanceTimersByTime(1000)

    expect(writer.current.value).toBe(frozen)
    expect(vi.getTimerCount()).toBe(0)
  })

  // The terminal has no exit, so it types until the page is refreshed. The
  // retained rows have to be trimmed or the array grows for as long as the tab
  // is left open.
  it('types indefinitely when no maxRows is given, keeping only keepRows', () => {
    const writer = useTypewriter({
      phrase: 'abc',
      keepRows: 3,
      charDelayMs: 10,
      rowDelayMs: 20,
      jitterRatio: 0,
    })
    writer.start()

    vi.advanceTimersByTime(2000)

    expect(writer.isDone.value).toBe(false)
    expect(writer.rows.value).toHaveLength(3)
    expect(vi.getTimerCount()).toBe(1)

    writer.stop()
  })

  it('restarts from an empty screen', () => {
    const writer = useTypewriter(OPTIONS)
    writer.start()
    vi.advanceTimersByTime(1000)
    expect(writer.rows.value).toHaveLength(2)

    writer.start()
    expect(writer.rows.value).toEqual([])
    expect(writer.isDone.value).toBe(false)
  })
})
