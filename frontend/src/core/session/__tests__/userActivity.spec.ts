import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { hasUnreportedActivity, IDLE_HEADER, idleHeaders, installUserActivityTracking } from '../userActivity'

describe('userActivity', () => {
  let stop: () => void

  beforeEach(() => {
    vi.useFakeTimers()
    stop = installUserActivityTracking()
  })

  afterEach(() => {
    stop()
    vi.useRealTimers()
  })

  it('reports the seconds since the last input, not since the last request', () => {
    window.dispatchEvent(new KeyboardEvent('keydown'))
    vi.advanceTimersByTime(90_000)

    expect(idleHeaders()).toEqual({ [IDLE_HEADER]: '90' })
    vi.advanceTimersByTime(30_000)
    expect(idleHeaders()).toEqual({ [IDLE_HEADER]: '120' })
  })

  it('knows when input has not been reported by any request yet', () => {
    idleHeaders()
    expect(hasUnreportedActivity()).toBe(false)

    vi.advanceTimersByTime(1000)
    window.dispatchEvent(new MouseEvent('pointerdown'))
    expect(hasUnreportedActivity()).toBe(true)

    idleHeaders()
    expect(hasUnreportedActivity()).toBe(false)
  })
})
