import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope, nextTick } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useSessionCountdown } from '../useSessionCountdown'

// Only setInterval/clearInterval are faked. Date.now() is driven by our
// own `clock` below instead of vi.setSystemTime(). That decouples "the wall
// clock jumped" from "a timer callback ran", which is exactly the point of
// the sleeping-tab test: a real browser coalesces every setInterval tick
// missed while suspended into a single catch-up fire, whereas vitest's
// fake-timer clock would otherwise replay each missed tick individually if
// Date were advanced via the timer clock itself.
let clock = 0

describe('useSessionCountdown', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    clock = new Date('2026-08-25T10:00:00.000Z').getTime()
    vi.spyOn(Date, 'now').mockImplementation(() => clock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('is inactive with no expiry set', () => {
    const scope = effectScope()
    const countdown = scope.run(() => useSessionCountdown())!

    expect(countdown.isActive.value).toBe(false)
    expect(countdown.remainingSeconds.value).toBe(0)
    expect(countdown.label.value).toBe('0:00')
    expect(countdown.isWarning.value).toBe(false)

    scope.stop()
  })

  it('formats the label as m:ss, including a single-digit minute and zero-padded seconds', () => {
    const store = useCurrentUserStore()
    store.sessionExpiresAt = clock + 14 * 60_000 + 59_000 // 14:59

    const scope = effectScope()
    const countdown = scope.run(() => useSessionCountdown())!

    expect(countdown.label.value).toBe('14:59')
    expect(countdown.isActive.value).toBe(true)
    expect(countdown.isWarning.value).toBe(false)

    scope.stop()
  })

  it('flags isWarning under 60 seconds remaining', () => {
    const store = useCurrentUserStore()
    store.sessionExpiresAt = clock + 7_000 // 0:07

    const scope = effectScope()
    const countdown = scope.run(() => useSessionCountdown())!

    expect(countdown.label.value).toBe('0:07')
    expect(countdown.isWarning.value).toBe(true)

    scope.stop()
  })

  it('recomputes remainingSeconds from the wall clock rather than decrementing, so a sleeping tab catches up in one tick', () => {
    const store = useCurrentUserStore()
    store.sessionExpiresAt = clock + 100_000

    const scope = effectScope()
    const countdown = scope.run(() => useSessionCountdown())!
    expect(countdown.remainingSeconds.value).toBe(100)

    // The tab sleeps: real time passes 90s but no interval callback runs
    // until the tab wakes and the browser fires exactly one catch-up tick.
    clock += 90_000
    vi.advanceTimersByTime(1000)

    expect(countdown.remainingSeconds.value).toBe(10)
    expect(countdown.label.value).toBe('0:10')

    scope.stop()
  })

  it('calls sessionExpired exactly once when the countdown reaches zero', async () => {
    const store = useCurrentUserStore()
    const sessionExpiredSpy = vi.spyOn(store, 'sessionExpired').mockImplementation(() => {})
    store.sessionExpiresAt = clock + 3_000

    const scope = effectScope()
    scope.run(() => useSessionCountdown())

    clock += 3_000
    vi.advanceTimersByTime(3_000)
    // watch()'s default 'pre' flush queues its callback on a microtask
    // rather than running synchronously, so it needs a tick to drain before
    // the call shows up.
    await nextTick()
    expect(sessionExpiredSpy).toHaveBeenCalledTimes(1)

    // Further ticks past zero must not call it again.
    clock += 5_000
    vi.advanceTimersByTime(5_000)
    await nextTick()
    expect(sessionExpiredSpy).toHaveBeenCalledTimes(1)

    scope.stop()
  })

  it('clears the interval once the expiry becomes null', async () => {
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
    const store = useCurrentUserStore()
    store.sessionExpiresAt = clock + 10_000

    const scope = effectScope()
    const countdown = scope.run(() => useSessionCountdown())!
    clock += 2000
    vi.advanceTimersByTime(2000)
    expect(countdown.remainingSeconds.value).toBe(8)

    store.sessionExpiresAt = null
    await nextTick()

    expect(clearIntervalSpy).toHaveBeenCalledTimes(1)
    expect(countdown.isActive.value).toBe(false)
    expect(countdown.remainingSeconds.value).toBe(0)

    scope.stop()
  })

  it('clears the interval on scope dispose (component unmount)', () => {
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
    const store = useCurrentUserStore()
    store.sessionExpiresAt = clock + 10_000

    const scope = effectScope()
    scope.run(() => useSessionCountdown())
    scope.stop()

    expect(clearIntervalSpy).toHaveBeenCalledTimes(1)
  })

  it('notifies again on a fresh expiry after a previous one already reached zero', async () => {
    const store = useCurrentUserStore()
    const sessionExpiredSpy = vi.spyOn(store, 'sessionExpired').mockImplementation(() => {})
    store.sessionExpiresAt = clock + 1_000

    const scope = effectScope()
    scope.run(() => useSessionCountdown())

    clock += 1_000
    vi.advanceTimersByTime(1_000)
    await nextTick()
    expect(sessionExpiredSpy).toHaveBeenCalledTimes(1)

    // A fresh session (e.g. signing back in) starts with time comfortably
    // remaining, not sitting at zero. watch() only fires on an actual
    // value change, so this must count down through nonzero values and
    // notify again rather than staying silenced by the first expiry.
    store.sessionExpiresAt = clock + 2_000
    await nextTick()

    clock += 2_000
    vi.advanceTimersByTime(2_000)
    await nextTick()
    expect(sessionExpiredSpy).toHaveBeenCalledTimes(2)

    scope.stop()
  })
})
