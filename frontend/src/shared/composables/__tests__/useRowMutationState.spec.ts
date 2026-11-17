import { describe, it, expect, vi } from 'vitest'

import { useRowMutationState } from '../useRowMutationState'

describe('useRowMutationState', () => {
  it('isPending is false for an id that never ran', () => {
    const { isPending } = useRowMutationState<number>()

    expect(isPending(1)).toBe(false)
  })

  it('marks an id pending for the duration of run()', async () => {
    const { isPending, run } = useRowMutationState<number>()
    let sawPendingInsideFn = false
    const fn = vi.fn<() => Promise<void>>(async () => {
      sawPendingInsideFn = isPending(5)
    })

    await run(5, fn)

    expect(sawPendingInsideFn).toBe(true)
    expect(isPending(5)).toBe(false)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('clears the id even when fn throws, and rethrows', async () => {
    const { isPending, run } = useRowMutationState<number>()
    const error = new Error('boom')
    const fn = vi.fn<() => Promise<void>>(async () => {
      throw error
    })

    await expect(run(5, fn)).rejects.toThrow(error)
    expect(isPending(5)).toBe(false)
  })

  it('tracks multiple ids independently', async () => {
    const { isPending, pending, run } = useRowMutationState<number>()
    let resolveFirst!: () => void
    const first = run(
      1,
      () =>
        new Promise<void>((resolve) => {
          resolveFirst = resolve
        }),
    )

    expect(isPending(1)).toBe(true)
    expect(isPending(2)).toBe(false)

    await run(2, async () => {})

    expect(isPending(1)).toBe(true)
    expect(isPending(2)).toBe(false)
    expect(pending.value.has(1)).toBe(true)

    resolveFirst()
    await first

    expect(isPending(1)).toBe(false)
  })
})
