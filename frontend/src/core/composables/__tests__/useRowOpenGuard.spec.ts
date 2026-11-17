import { describe, it, expect, vi } from 'vitest'

import { useRowOpenGuard } from '../useRowOpenGuard'

describe('useRowOpenGuard', () => {
  it('runs the callback immediately on the first call for a key', () => {
    const { guard } = useRowOpenGuard<number>()
    const fn = vi.fn<() => void>()

    guard(1, fn)

    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('mirrors a mouse click on an unselected row: row-click then row-select fire synchronously - only one open', () => {
    const { guard } = useRowOpenGuard<number>()
    const open = vi.fn<(id?: number) => void>()

    // Both OpenVue emits happen back-to-back in the same call stack for
    // the same row.
    guard(1, () => open(1))
    guard(1, () => open(1))

    expect(open).toHaveBeenCalledTimes(1)
  })

  it('does not suppress a call for a different row in the same tick', () => {
    const { guard } = useRowOpenGuard<number>()
    const open = vi.fn<(id?: number) => void>()

    guard(1, () => open(1))
    guard(2, () => open(2))

    expect(open).toHaveBeenCalledTimes(2)
    expect(open).toHaveBeenNthCalledWith(1, 1)
    expect(open).toHaveBeenNthCalledWith(2, 2)
  })

  it('runs the callback again for the same row once the microtask queue has drained', async () => {
    const { guard } = useRowOpenGuard<number>()
    const open = vi.fn<(id?: number) => void>()

    guard(1, () => open(1))
    await Promise.resolve()
    guard(1, () => open(1))

    expect(open).toHaveBeenCalledTimes(2)
  })
})
