import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'

import { useCountUp } from '../useCountUp'

// requestAnimationFrame under vitest's fake timers fires on a simulated
// ~16ms cadence (not driven by wall-clock advanceTimersByTime deltas
// matching the animation's own elapsed-time math 1:1), so exact
// intermediate values aren't asserted here; only that the animation
// lands exactly on the target once its full duration has elapsed, and
// that it's moving in the right direction partway through.
describe('useCountUp', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts displaying the initial target value with no animation', () => {
    const target = ref(42)
    const displayed = useCountUp(target)
    expect(displayed.value).toBe(42)
  })

  it('animates from the previous target to the next one, landing exactly on it after the duration', async () => {
    const target = ref(0)
    const displayed = useCountUp(target, 200)

    target.value = 100
    await nextTick()
    vi.advanceTimersByTime(250)

    expect(displayed.value).toBe(100)
  })

  it('is partway between start and target before the duration has elapsed', async () => {
    const target = ref(0)
    const displayed = useCountUp(target, 600)

    target.value = 100
    await nextTick()
    vi.advanceTimersByTime(300)

    expect(displayed.value).toBeGreaterThan(0)
    expect(displayed.value).toBeLessThan(100)
  })

  it('animates downward just as well as upward', async () => {
    const target = ref(100)
    const displayed = useCountUp(target, 200)

    target.value = 20
    await nextTick()
    vi.advanceTimersByTime(250)

    expect(displayed.value).toBe(20)
  })

  it('a second target change before the first animation finishes cancels the stale frame and still lands on the latest target', async () => {
    const target = ref(0)
    const displayed = useCountUp(target, 400)

    target.value = 50
    await nextTick()
    vi.advanceTimersByTime(100)

    target.value = 10
    await nextTick()
    vi.advanceTimersByTime(450)

    expect(displayed.value).toBe(10)
  })

  it('defaults to a 600ms duration when none is given', async () => {
    const target = ref(0)
    const displayed = useCountUp(target)

    target.value = 5
    await nextTick()
    // Not yet at the default 600ms mark.
    vi.advanceTimersByTime(100)
    expect(displayed.value).not.toBe(5)

    vi.advanceTimersByTime(600)
    expect(displayed.value).toBe(5)
  })
})
