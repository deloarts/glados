import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { LiveSignal } from '@/core/realtime/types'
import type { ControlledDocument } from '../types'

const subscribers = new Map<string, (signal: LiveSignal) => void>()
const fakeLiveStore = reactive({
  reconnectCount: 0,
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})
vi.mock('@/core/realtime/liveStore', () => ({ useLiveStore: () => fakeLiveStore }))

import { installUserActivityTracking } from '@/core/session/userActivity'
import { LOCK_IDLE_MS, LOCK_RENEW_MS, useDocumentLock } from '../composables/useDocumentLock'

function doc(overrides: Partial<ControlledDocument> = {}): ControlledDocument {
  return {
    id: 7,
    document_number: 'CHK-26-0007',
    revision: 'B',
    is_latest: true,
    superseded_at: null,
    read_only: false,
    released_at: null,
    released_by_full_name: null,
    invalid_at: null,
    invalid_by_full_name: null,
    invalid_reason: null,
    locked_by_id: null,
    locked_by_full_name: null,
    locked_at: null,
    lock_expires_at: null,
    ...overrides,
  }
}

const mine = { locked_by_id: 1, locked_by_full_name: 'Me', locked_at: '2026-10-20T10:00:00Z' }
const theirs = { locked_by_id: 2, locked_by_full_name: 'Jane Doe', locked_at: '2026-10-20T10:05:00Z' }

function setup(initial: ControlledDocument) {
  const document = ref<ControlledDocument | null>(initial)
  const lock = vi.fn<(id: number, takeOver: boolean) => Promise<ControlledDocument>>(async () => doc(mine))
  const unlock = vi.fn<(id: number) => Promise<ControlledDocument>>(async () => doc())
  const reload = vi.fn<(id: number) => Promise<ControlledDocument>>(async () => document.value!)
  const onLost = vi.fn<(by: string | null) => void>()
  const onIdle = vi.fn<() => void>()
  const scope = effectScope()
  const api = scope.run(() =>
    useDocumentLock({
      document,
      resource: 'checklists',
      lock,
      unlock,
      reload,
      apply: (loaded) => (document.value = loaded),
      onLost,
      onIdle,
    }),
  )!
  return { document, lock, unlock, reload, onLost, onIdle, scope, api }
}

const stopTracking = installUserActivityTracking()
afterAll(() => stopTracking())

describe('useDocumentLock', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useCurrentUserStore().user = { id: 1, permissions: [], is_systemuser: false } as never
    subscribers.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('takes the lock on Edit, renews its lease while the user works and ends it on Done', async () => {
    const { api, lock, unlock } = setup(doc())
    expect(api.editing.value).toBe(false)

    await api.startEditing()
    expect(lock).toHaveBeenCalledWith(7, false)
    expect(api.editing.value).toBe(true)

    await vi.advanceTimersByTimeAsync(60_000)
    window.dispatchEvent(new KeyboardEvent('keydown'))
    await vi.advanceTimersByTimeAsync(LOCK_RENEW_MS)
    expect(lock).toHaveBeenCalledTimes(2)

    await api.stopEditing()
    expect(unlock).toHaveBeenCalledWith(7)
    expect(api.editing.value).toBe(false)
  })

  it('does not renew the lease of a page nobody works on, and ends its editing before the lease runs out', async () => {
    // Input recorded by earlier tests lies well in the past.
    vi.setSystemTime(Date.now() + 24 * 60 * 60 * 1000)
    const { api, lock, unlock, onIdle } = setup(doc())
    await api.startEditing()

    await vi.advanceTimersByTimeAsync(LOCK_RENEW_MS + 60_000)
    expect(lock).toHaveBeenCalledTimes(1)
    expect(onIdle).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(LOCK_IDLE_MS - LOCK_RENEW_MS)
    expect(unlock).toHaveBeenCalledWith(7)
    expect(api.editing.value).toBe(false)
    expect(onIdle).toHaveBeenCalledOnce()
  })

  it('shows who else edits the document', () => {
    const { api } = setup(doc(theirs))
    expect(api.editing.value).toBe(false)
    expect(api.lockedByOther.value).toEqual({ name: 'Jane Doe', since: '2026-10-20T10:05:00Z' })
  })

  it('tells the page when a live change shows its lock was taken over', async () => {
    const { reload, onLost } = setup(doc(mine))
    reload.mockResolvedValue(doc(theirs))

    subscribers.get('checklists')?.({ resource: 'checklists', id: 7, action: 'updated', actor_id: 2 })
    await vi.runOnlyPendingTimersAsync()
    await nextTick()

    expect(reload).toHaveBeenCalledWith(7)
    expect(onLost).toHaveBeenCalledWith('Jane Doe')
  })

  it('ignores changes of other documents and ends editing when the page goes away', async () => {
    const { reload, unlock, scope } = setup(doc(mine))
    subscribers.get('checklists')?.({ resource: 'checklists', id: 99, action: 'updated', actor_id: 2 })
    expect(reload).not.toHaveBeenCalled()

    scope.stop()
    expect(unlock).toHaveBeenCalledWith(7)
    expect(subscribers.has('checklists')).toBe(false)
  })
})
