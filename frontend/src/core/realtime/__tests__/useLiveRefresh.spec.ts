import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'

import type { LiveSignal } from '../types'

// The fake store is reactive() so `live.reconnectCount` auto-unwraps like it
// does on the Pinia store, which the reconnect watch relies on.
const fakeReconnectCount = ref(0)
const subscribers = new Map<string, Set<(signal: LiveSignal) => void>>()

const fakeLiveStore = reactive({
  reconnectCount: fakeReconnectCount,
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    const set = subscribers.get(resource) ?? new Set()
    set.add(handler)
    subscribers.set(resource, set)
    return () => set.delete(handler)
  },
})

vi.mock('../liveStore', () => ({
  useLiveStore: () => fakeLiveStore,
}))

import { useLiveRefresh } from '../useLiveRefresh'
import type { UseLiveRefreshOptions } from '../useLiveRefresh'

function emit(resource: string, id = 1, action: LiveSignal['action'] = 'updated'): void {
  subscribers.get(resource)?.forEach((handler) => handler({ resource, id, action, actor_id: null }))
}

function setup(refetch: () => unknown, options?: UseLiveRefreshOptions) {
  const scope = effectScope()
  scope.run(() => useLiveRefresh(['orders', 'lots'], refetch, options))
  return scope
}

describe('useLiveRefresh', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    subscribers.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces signals on any watched resource into one refetch', async () => {
    const refetch = vi.fn<() => void>()
    const scope = setup(refetch)

    emit('orders')
    await vi.advanceTimersByTimeAsync(300)
    emit('lots')
    await vi.advanceTimersByTimeAsync(499)
    expect(refetch).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(refetch).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('honours a custom debounce window', async () => {
    const refetch = vi.fn<() => void>()
    const scope = setup(refetch, { debounceMs: 100 })

    emit('orders')
    await vi.advanceTimersByTimeAsync(100)

    expect(refetch).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('ignores a signal the filter rejects', async () => {
    const refetch = vi.fn<() => void>()
    const scope = setup(refetch, { filter: (signal) => signal.id === 7 })

    emit('orders', 3)
    await vi.advanceTimersByTimeAsync(1000)
    expect(refetch).not.toHaveBeenCalled()

    emit('orders', 7)
    await vi.advanceTimersByTimeAsync(1000)
    expect(refetch).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('refetches once right away after a reconnect and drops a pending debounce', async () => {
    const refetch = vi.fn<() => void>()
    const scope = setup(refetch)

    emit('orders')
    fakeReconnectCount.value++
    await nextTick()
    expect(refetch).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1000)
    expect(refetch).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('handles a rejected or throwing refetch', async () => {
    const unhandled = vi.fn<(reason: unknown) => void>()
    process.on('unhandledRejection', unhandled)
    const rejecting = vi.fn<() => Promise<void>>().mockRejectedValue(new Error('offline'))
    const throwing = vi.fn<() => void>(() => {
      throw new Error('boom')
    })
    const scopes = [setup(rejecting), setup(throwing)]

    emit('orders')
    await vi.advanceTimersByTimeAsync(500)
    await Promise.resolve()

    expect(rejecting).toHaveBeenCalledTimes(1)
    expect(throwing).toHaveBeenCalledTimes(1)
    expect(unhandled).not.toHaveBeenCalled()
    process.off('unhandledRejection', unhandled)
    scopes.forEach((scope) => scope.stop())
  })

  it('stops listening when its scope is disposed', async () => {
    const refetch = vi.fn<() => void>()
    const scope = setup(refetch)

    emit('orders')
    scope.stop()
    await vi.advanceTimersByTimeAsync(1000)
    emit('orders')
    fakeReconnectCount.value++
    await nextTick()

    expect(refetch).not.toHaveBeenCalled()
  })
})
