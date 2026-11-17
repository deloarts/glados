import { describe, it, expect, vi, beforeEach } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'

import type { LiveSignal } from '@/core/realtime/types'

// Mirrors useLiveRows.spec.ts's fake liveStore: a reactive wrapper so
// `() => liveStore.reconnectCount` stays reactive under Pinia's
// ref-auto-unwrap behaviour, and a subscriber map standing in for
// liveStore.on()/its returned unsubscribe.
const fakeReconnectCount = ref(0)
const subscribers = new Map<string, (signal: LiveSignal) => void>()

const fakeLiveStore = reactive({
  reconnectCount: fakeReconnectCount,
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})

vi.mock('@/core/realtime/liveStore', () => ({
  useLiveStore: () => fakeLiveStore,
}))

const fetchStatusMock = vi.fn<() => Promise<void>>()

vi.mock('../../stores/autoPlanRunStore', () => ({
  useAutoPlanRunStore: () => ({ fetchStatus: fetchStatusMock }),
}))

import { useAutoPlanRunLiveSync } from '../useAutoPlanRunLiveSync'

function emit(resource: string, signal: LiveSignal): void {
  subscribers.get(resource)?.(signal)
}

describe('useAutoPlanRunLiveSync', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    subscribers.clear()
    fetchStatusMock.mockReset()
    fetchStatusMock.mockResolvedValue(undefined)
  })

  it('fetches status once immediately on subscribe, so a page load during a run shows it', () => {
    const scope = effectScope()
    scope.run(() => useAutoPlanRunLiveSync())

    expect(fetchStatusMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('refetches on a signal for the auto-plan-run resource', () => {
    const scope = effectScope()
    scope.run(() => useAutoPlanRunLiveSync())
    fetchStatusMock.mockClear()

    emit('auto-plan-run', { resource: 'auto-plan-run', id: 0, action: 'updated', actor_id: 7 })

    expect(fetchStatusMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('ignores a signal for a different resource', () => {
    const scope = effectScope()
    scope.run(() => useAutoPlanRunLiveSync())
    fetchStatusMock.mockClear()

    emit('production-lots', { resource: 'production-lots', id: 1, action: 'created', actor_id: null })

    expect(fetchStatusMock).not.toHaveBeenCalled()
    scope.stop()
  })

  it('refetches on a reconnectCount bump (missed-signal recovery)', async () => {
    const scope = effectScope()
    scope.run(() => useAutoPlanRunLiveSync())
    fetchStatusMock.mockClear()

    fakeReconnectCount.value++
    await nextTick()

    expect(fetchStatusMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('unsubscribes on scope dispose - a later signal is silently ignored', () => {
    const scope = effectScope()
    scope.run(() => useAutoPlanRunLiveSync())
    scope.stop()
    fetchStatusMock.mockClear()

    emit('auto-plan-run', { resource: 'auto-plan-run', id: 0, action: 'updated', actor_id: null })

    expect(fetchStatusMock).not.toHaveBeenCalled()
  })
})
