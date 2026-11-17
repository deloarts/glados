import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { LiveResource } from '@/core/realtime/resources'
import { makeUserResponse } from '@/test-utils/factories'
import type { LiveSignal } from '@/core/realtime/types'

import { useAnnouncementsStore } from '../../stores/announcementsStore'

// Mirrors useAutoPlanRunLiveSync.spec.ts's fake liveStore, a reactive
// wrapper so `() => liveStore.reconnectCount` stays reactive, and a
// subscriber map standing in for liveStore.on()/its returned unsubscribe,
// with full control over when a signal "arrives" and whether unsubscribe
// was actually called.
const fakeReconnectCount = ref(0)
const subscribers = new Map<string, (signal: LiveSignal) => void>()
const unsubscribeMock = vi.fn<() => void>()

const fakeLiveStore = reactive({
  reconnectCount: fakeReconnectCount,
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return unsubscribeMock
  },
})

vi.mock('@/core/realtime/liveStore', () => ({
  useLiveStore: () => fakeLiveStore,
}))

function fireSignal(): void {
  subscribers.get(LiveResource.ANNOUNCEMENTS)?.({
    resource: LiveResource.ANNOUNCEMENTS,
    id: 1,
    action: 'updated',
    actor_id: null,
  })
}

import AnnouncementsHandler from '../AnnouncementsHandler.vue'

function setUp() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const currentUserStore = useCurrentUserStore()
  const announcementsStore = useAnnouncementsStore()

  const refreshSpy = vi.spyOn(announcementsStore, 'refresh').mockResolvedValue(undefined)
  const startTickingSpy = vi.spyOn(announcementsStore, 'startTicking')
  const stopTickingSpy = vi.spyOn(announcementsStore, 'stopTicking')

  const wrapper = mount(AnnouncementsHandler, { global: { plugins: [pinia] } })

  return { wrapper, currentUserStore, announcementsStore, refreshSpy, startTickingSpy, stopTickingSpy }
}

describe('AnnouncementsHandler', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    subscribers.clear()
    unsubscribeMock.mockClear()
  })

  it('does nothing while signed out', async () => {
    const { refreshSpy, startTickingSpy } = setUp()
    await flushPromises()

    expect(refreshSpy).not.toHaveBeenCalled()
    expect(startTickingSpy).not.toHaveBeenCalled()
  })

  it('refreshes and starts ticking once signed in', async () => {
    const { currentUserStore, refreshSpy, startTickingSpy } = setUp()

    currentUserStore.user = makeUserResponse()
    await flushPromises()

    expect(startTickingSpy).toHaveBeenCalledTimes(1)
    expect(refreshSpy).toHaveBeenCalledTimes(1)
  })

  it('refetches on the live "announcements" signal', async () => {
    const { currentUserStore, refreshSpy } = setUp()
    currentUserStore.user = makeUserResponse()
    await flushPromises()
    expect(refreshSpy).toHaveBeenCalledTimes(1)

    fireSignal()
    await flushPromises()

    expect(refreshSpy).toHaveBeenCalledTimes(2)
  })

  it('refetches on a stream reconnect', async () => {
    const { currentUserStore, refreshSpy } = setUp()
    currentUserStore.user = makeUserResponse()
    await flushPromises()
    expect(refreshSpy).toHaveBeenCalledTimes(1)

    fakeReconnectCount.value++
    await flushPromises()

    expect(refreshSpy).toHaveBeenCalledTimes(2)
  })

  it('stops ticking and unsubscribes on logout, and no longer refetches on reconnect', async () => {
    const { currentUserStore, refreshSpy, stopTickingSpy } = setUp()
    // The watcher's immediate:true initial run (isAuthenticated starting
    // false) already calls stopTicking() once, the same harmless no-op
    // LiveConnectionHandler's own start/stop pattern has on a signed-out
    // mount; only the call *after* signing in proves logout itself
    // stopped it.
    const stopTickingCallsBeforeLogout = stopTickingSpy.mock.calls.length

    currentUserStore.user = makeUserResponse()
    await flushPromises()
    expect(refreshSpy).toHaveBeenCalledTimes(1)

    currentUserStore.user = null
    await flushPromises()

    expect(stopTickingSpy.mock.calls.length - stopTickingCallsBeforeLogout).toBe(1)
    expect(unsubscribeMock).toHaveBeenCalledTimes(1)

    fakeReconnectCount.value++
    await flushPromises()

    // Still just the one call from the earlier sign-in; the reconnect
    // watch is guarded by isAuthenticated independently of the live
    // subscription itself.
    expect(refreshSpy).toHaveBeenCalledTimes(1)
  })
})
