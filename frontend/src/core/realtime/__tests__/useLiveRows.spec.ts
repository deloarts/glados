import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'
import type { Ref } from 'vue'

import type { LiveAction, LiveSignal } from '../types'

// useLiveRows watches `live.reconnectCount` via a plain property read
// (`() => live.reconnectCount`), relying on Pinia's ref-auto-unwrap on the
// store instance for that to be reactive. `reactive()` gives the same
// auto-unwrap behavior, so the fake must be wrapped in it too, not a plain
// object, or the reconnect-recovery watch below would silently never fire.
const fakeReconnectCount = ref(0)
const subscribers = new Map<string, (signal: LiveSignal) => void>()

const fakeLiveStore = reactive({
  reconnectCount: fakeReconnectCount,
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})

vi.mock('../liveStore', () => ({
  useLiveStore: () => fakeLiveStore,
}))

import { useLiveRows } from '../useLiveRows'

interface Row {
  id: number
  name: string
}

function emit(resource: string, id: number, action: LiveAction): void {
  subscribers.get(resource)?.({ resource, id, action, actor_id: null })
}

function setup(items: Ref<Row[]>, total: Ref<number>) {
  const fetchByIds = vi.fn<(ids: number[]) => Promise<Row[]>>().mockResolvedValue([])
  const onFullRefresh = vi.fn<() => void>()
  const scope = effectScope()
  scope.run(() => {
    useLiveRows<Row>({ resource: 'orders', items, total, fetchByIds, onFullRefresh })
  })
  return { fetchByIds, onFullRefresh, scope }
}

describe('useLiveRows', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    subscribers.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('ignores an updated signal for a row not currently visible', async () => {
    const items = ref<Row[]>([{ id: 1, name: 'a' }])
    const total = ref(1)
    const { fetchByIds, scope } = setup(items, total)

    emit('orders', 999, 'updated')
    await vi.advanceTimersByTimeAsync(1000)

    expect(fetchByIds).not.toHaveBeenCalled()
    scope.stop()
  })

  it('coalesces two updated signals within the window into one fetchByIds call with both ids', async () => {
    const items = ref<Row[]>([
      { id: 1, name: 'a' },
      { id: 2, name: 'b' },
    ])
    const total = ref(2)
    const { fetchByIds, scope } = setup(items, total)

    emit('orders', 1, 'updated')
    emit('orders', 2, 'updated')
    await vi.advanceTimersByTimeAsync(300)

    expect(fetchByIds).toHaveBeenCalledTimes(1)
    expect(fetchByIds.mock.calls[0]![0].sort()).toEqual([1, 2])
    scope.stop()
  })

  it('replaces a row in place at its existing index, leaving others untouched', async () => {
    const items = ref<Row[]>([
      { id: 1, name: 'a' },
      { id: 2, name: 'b' },
    ])
    const total = ref(2)
    const { fetchByIds, onFullRefresh, scope } = setup(items, total)
    fetchByIds.mockResolvedValue([{ id: 2, name: 'b2' }])

    emit('orders', 2, 'updated')
    await vi.advanceTimersByTimeAsync(300)

    expect(items.value[0]).toEqual({ id: 1, name: 'a' })
    expect(items.value[1]).toEqual({ id: 2, name: 'b2' })
    expect(onFullRefresh).not.toHaveBeenCalled()
    scope.stop()
  })

  it('falls back to a full refresh when a requested id is missing from the response', async () => {
    const items = ref<Row[]>([{ id: 1, name: 'a' }])
    const total = ref(1)
    const { onFullRefresh, scope } = setup(items, total)
    // fetchByIds already resolves [] via setup(): simulates the row
    // having left the filtered set (e.g. a status change).

    emit('orders', 1, 'updated')
    await vi.advanceTimersByTimeAsync(300)

    expect(onFullRefresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('deleted splices the row and decrements total, with no fetch at all', () => {
    const items = ref<Row[]>([
      { id: 1, name: 'a' },
      { id: 2, name: 'b' },
    ])
    const total = ref(2)
    const { fetchByIds, scope } = setup(items, total)

    emit('orders', 1, 'deleted')

    expect(items.value).toEqual([{ id: 2, name: 'b' }])
    expect(total.value).toBe(1)
    expect(fetchByIds).not.toHaveBeenCalled()
    scope.stop()
  })

  it('deleted for an id not present is a no-op, total never goes negative', () => {
    const items = ref<Row[]>([{ id: 1, name: 'a' }])
    const total = ref(0) // already inconsistent on purpose, guards Math.max(0, ...)
    const { scope } = setup(items, total)

    emit('orders', 999, 'deleted')

    expect(items.value).toEqual([{ id: 1, name: 'a' }])
    expect(total.value).toBe(0)
    scope.stop()
  })

  it('created triggers an immediate full refresh without touching fetchByIds', () => {
    const items = ref<Row[]>([])
    const total = ref(0)
    const { fetchByIds, onFullRefresh, scope } = setup(items, total)

    emit('orders', 5, 'created')

    expect(onFullRefresh).toHaveBeenCalledTimes(1)
    expect(fetchByIds).not.toHaveBeenCalled()
    scope.stop()
  })

  it('bulk triggers an immediate full refresh', () => {
    const items = ref<Row[]>([])
    const total = ref(0)
    const { onFullRefresh, scope } = setup(items, total)

    emit('orders', 0, 'bulk')

    expect(onFullRefresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('a signal for a different resource is not dispatched to this subscription', () => {
    const items = ref<Row[]>([{ id: 1, name: 'a' }])
    const total = ref(1)
    const { onFullRefresh, scope } = setup(items, total)

    emit('production-lots', 1, 'created')

    expect(onFullRefresh).not.toHaveBeenCalled()
    scope.stop()
  })

  it('a reconnectCount bump triggers a full refresh (missed-update recovery)', async () => {
    const items = ref<Row[]>([])
    const total = ref(0)
    const { onFullRefresh, scope } = setup(items, total)

    fakeReconnectCount.value++
    await nextTick()

    expect(onFullRefresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('unsubscribes on scope dispose - a later signal is silently ignored', () => {
    const items = ref<Row[]>([{ id: 1, name: 'a' }])
    const total = ref(1)
    const { scope } = setup(items, total)
    scope.stop()

    emit('orders', 1, 'deleted')

    expect(items.value).toEqual([{ id: 1, name: 'a' }])
  })
})
