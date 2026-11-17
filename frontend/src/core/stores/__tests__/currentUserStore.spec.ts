import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia, defineStore } from 'pinia'
import { nextTick, createApp, ref, watch } from 'vue'

const pushMock = vi.fn<(...args: unknown[]) => void>()

vi.mock('@/router', () => ({
  default: {
    push: (...args: unknown[]) => pushMock(...args),
    currentRoute: { value: { name: 'Dashboard', fullPath: '/dashboard' } },
  },
}))

const getUserAvatarMock = vi.fn<(userId: number) => Promise<Blob | null>>()

vi.mock('@/core/api/users/getUserAvatar', () => ({
  getUserAvatar: (userId: number) => getUserAvatarMock(userId),
}))

const getCurrentUserMock = vi.fn<() => Promise<UserResponse>>()

vi.mock('@/core/api/users/getCurrentUser', () => ({
  getCurrentUser: () => getCurrentUserMock(),
}))

const getCurrentSessionMock = vi.fn<() => Promise<CurrentSessionResult>>()

vi.mock('@/core/api/users/getCurrentSession', () => ({
  getCurrentSession: () => getCurrentSessionMock(),
}))

const postLogoutMock = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)

vi.mock('@/core/api/users/postLogout', () => ({
  postLogout: () => postLogoutMock(),
}))

import { useCurrentUserStore, SYSTEM_USER_WARNING_SESSION_KEY } from '../currentUserStore'
import { useUserAvatarsStore } from '../userAvatarsStore'
import { storeResetPlugin, BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '../resetOnLogout'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { makeUserResponse } from '@/test-utils/factories'

import type { PageResponse } from '@/core/api/types'
import type { UserResponse } from '@/core/types/userResponse'
import type { CurrentSessionResult } from '@/core/api/users/getCurrentSession'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers. Mirrors the helper in
 * useSequencedFetch.spec.ts / productionLotsStore.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

/**
 * Small stand-ins for a real feature store, defined locally so this core
 * spec can prove logout()'s generic reset/draft-clearing/epoch-discard
 * behaviour (resetOnLogout.ts) without a core spec importing from features;
 * any store shaped like these is affected exactly the same way, whichever
 * feature owns it.
 */

// Mirrors a demand-import draft store's persistence shape (see
// src/shared/demand-import/stores/createDemandImportDraftStore.ts, which
// bought-items/made-items both instantiate) closely enough to exercise
// clearPersistedDrafts() against the real storage key it sweeps.
const useTestDraftStore = defineStore('testDraftStore', () => {
  const step = ref<'upload' | 'mapColumns' | 'review'>('upload')
  const headers = ref<string[]>([])

  watch(
    [step, headers],
    () => {
      localStorage.setItem(
        BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
        JSON.stringify({ step: step.value, headers: headers.value }),
      )
    },
    { deep: true },
  )

  return { step, headers }
})

// Mirrors a useSequencedFetch-backed list store (e.g. productionLotsStore)
// closely enough to exercise resetAllStores()'s fetch-epoch guard against a
// refresh() that resolves after logout() has already reset the store.
const fetchItemsMock = vi.fn<() => Promise<PageResponse<{ id: number }>>>()

const useTestListStore = defineStore('testListStore', () => {
  const { loading, error, run } = useSequencedFetch(fetchItemsMock)
  const items = ref<{ id: number }[]>([])
  const total = ref(0)

  async function refresh(): Promise<void> {
    const response = await run()
    if (!response) return
    items.value = response.items
    total.value = response.total
  }

  return { loading, error, items, total, refresh }
})

// The session lives in an httponly cookie the page script cannot clear
// itself (that is the whole point, see M2), so every path that ends a
// session client-side must also ask the backend to clear it server-side.
describe('currentUserStore, session cookie cleared on session end', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('calls postLogout on a deliberate logout()', () => {
    useCurrentUserStore().logout()

    expect(postLogoutMock).toHaveBeenCalledOnce()
  })

  it('calls postLogout when the session expires underneath the user', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse()

    store.sessionExpired()

    expect(postLogoutMock).toHaveBeenCalledOnce()
  })

  it('tears down client-side state even when postLogout itself fails', async () => {
    postLogoutMock.mockRejectedValueOnce(new Error('network error'))

    const store = useCurrentUserStore()
    store.user = makeUserResponse()
    store.logout()
    await Promise.resolve() // let the fire-and-forget rejection settle

    expect(store.user).toBeNull()
  })
})

// Cached avatars are blob object URLs (URL.createObjectURL), and nothing
// else revokes them, so a session ending without this leaked one blob per
// distinct avatar ever viewed, for the rest of the tab's life.
describe('currentUserStore, avatar cache cleanup on session end', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // jsdom does not implement these; assign stubs directly rather than
    // vi.spyOn, which requires the method to exist first.
    URL.createObjectURL = vi.fn<() => string>().mockReturnValue('blob:fake')
    URL.revokeObjectURL = vi.fn<() => void>()
  })

  it('revokes every cached avatar blob URL on logout', async () => {
    getUserAvatarMock.mockResolvedValue(new Blob(['x']))
    const avatars = useUserAvatarsStore()
    await avatars.fetch(1)
    await avatars.fetch(2)

    useCurrentUserStore().logout()

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
    expect(avatars.get(1)).toBeNull()
    expect(avatars.get(2)).toBeNull()
  })

  it('revokes every cached avatar blob URL when the session expires', async () => {
    getUserAvatarMock.mockResolvedValue(new Blob(['x']))
    const store = useCurrentUserStore()
    store.user = { id: 1 } as never
    const avatars = useUserAvatarsStore()
    await avatars.fetch(1)

    store.sessionExpired()

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1)
    expect(avatars.get(1)).toBeNull()
  })

  it('does not revoke anything when nothing was cached', () => {
    useCurrentUserStore().logout()

    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
  })
})

// logout()/sessionExpired() must reset every other store to its
// initial state and clear any persisted draft, so the next sign-in on this
// tab (a shared machine, most of all) never sees the previous session's
// data. Unlike the suite above, these seed a *fresh* pinia with
// storeResetPlugin registered. The plugin is only active where main.ts (or
// a test) installs it, so this is the one place that exercises the real
// wiring end to end rather than just resetOnLogout.ts in isolation.
describe('currentUserStore, full store reset + draft clearing on session end', () => {
  beforeEach(() => {
    const pinia = createPinia()
    // pinia.use() only queues the plugin unless the pinia instance is
    // already installed into a Vue app (see resetOnLogout.spec.ts's
    // freshPinia for the full explanation). app.use(pinia) here is a
    // throwaway stand-in for what main.ts's real app.use(pinia) does.
    const app = createApp({})
    app.use(pinia)
    pinia.use(storeResetPlugin)
    setActivePinia(pinia)
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('logout() resets a seeded feature store and clears the persisted batch-import draft', () => {
    const draftStore = useTestDraftStore()
    draftStore.step = 'review'
    draftStore.headers = ['Item', 'Qty']
    expect(draftStore.step).toBe('review')

    // Simulates what the store's own persistence watcher would eventually
    // write. It is set directly rather than awaiting the watcher, so this
    // doesn't depend on Vue's flush timing to set up the scenario.
    localStorage.setItem(
      BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
      JSON.stringify({ step: 'review', headers: ['Item', 'Qty'] }),
    )

    useCurrentUserStore().logout()

    expect(draftStore.step).toBe('upload')
    expect(draftStore.headers).toEqual([])
    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).toBeNull()
  })

  it('sessionExpired() resets a seeded feature store, clears the draft, and still preserves the redirect query', () => {
    const draftStore = useTestDraftStore()
    draftStore.step = 'mapColumns'
    localStorage.setItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY, JSON.stringify({ step: 'mapColumns' }))

    const store = useCurrentUserStore()
    store.user = { id: 1 } as never // past the "already signed out" no-op guard

    store.sessionExpired()

    expect(draftStore.step).toBe('upload')
    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).toBeNull()
    // The whole reason sessionExpired() can't just location.reload(): the
    // redirect query it builds must survive the reset untouched.
    expect(pushMock).toHaveBeenCalledWith({
      name: 'Login',
      query: { reason: 'expired', redirect: '/dashboard' },
    })
  })

  it("logout() leaves layoutStore's dark-mode preference untouched", async () => {
    const { useLayoutStore } = await import('../layoutStore')
    const layout = useLayoutStore()
    layout.setDarkMode(true)

    useCurrentUserStore().logout()

    expect(layout.isDarkMode).toBe(true)
  })

  it("logout() leaves hostStore's fetched feature flags untouched", async () => {
    const { useHostStore } = await import('@/core/host/stores/hostStore')
    const host = useHostStore()
    host.productionPlanningEnabled = false

    useCurrentUserStore().logout()

    expect(host.productionPlanningEnabled).toBe(false)
  })

  // The display timezone is the tenant's, applied from the host capabilities
  // that survive logout, so the next sign-in renders in it too.
  it('logout() keeps the tenant display timezone', async () => {
    const { getDisplayTimezone, setDisplayTimezone } = await import('@/core/utils/dates')
    setDisplayTimezone('Asia/Tokyo')

    useCurrentUserStore().logout()

    expect(getDisplayTimezone()).toBe('Asia/Tokyo')
    setDisplayTimezone(null)
  })

  it('logout() does not touch the batch-draft key when there was never a draft', () => {
    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).toBeNull()

    expect(() => useCurrentUserStore().logout()).not.toThrow()

    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).toBeNull()
  })

  // A `useSequencedFetch`-backed store's refresh() can still be in
  // flight when logout() runs. resetAllStores() empties the store
  // synchronously, but the in-flight request is untouched by that reset
  // and would land moments later straight into `items.value =
  // response.items`, quietly repopulating the just-reset store with the
  // previous user's data. bumpFetchEpoch() (called from resetAllStores();
  // see resetOnLogout.ts) closes this: the response is discarded, silently,
  // once it notices the epoch moved on.
  it('discards a store refresh() response that resolves after logout() interrupts it mid-flight, instead of repopulating the reset store', async () => {
    const inFlight = deferred<PageResponse<{ id: number }>>()
    fetchItemsMock.mockReturnValue(inFlight.promise)

    const listStore = useTestListStore()
    const refreshCall = listStore.refresh()
    expect(listStore.loading).toBe(true)

    // logout() fires while the above refresh() is still awaiting the API.
    useCurrentUserStore().logout()

    // The stale request finally resolves, now that resetAllStores() has
    // both emptied the store and bumped the fetch epoch.
    inFlight.resolve({ items: [{ id: 1 }], total: 1, limit: null, skip: 0 })
    await refreshCall

    expect(listStore.items).toEqual([])
    expect(listStore.total).toBe(0)
    expect(listStore.loading).toBe(false)
    expect(listStore.error).toBeNull()
  })

  it("the batch-draft store's own persistence watcher does not resurrect the draft key after logout() clears it", async () => {
    // resetAllStores() patches the draft store back to empty, which is
    // itself a change the store's `watch(..., persist, {deep:true})` reacts
    // to, but only on a later microtask (Vue's default 'pre' flush), so
    // without clearPersistedDrafts's own nextTick() follow-up the key would
    // be back a tick after logout() returns (verified empirically while
    // building this: it came back holding the already-reset empty draft,
    // never the stale one; not a data leak, but not "cleared" either).
    const draftStore = useTestDraftStore()
    draftStore.step = 'review'
    draftStore.headers = ['Item']
    await nextTick()
    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).not.toBeNull()

    useCurrentUserStore().logout()
    await nextTick()

    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).toBeNull()
  })
})

// sessionExpiresAt is the header countdown's data source, populated only
// for the one account whose session hard-expires (is_systemuser), and
// skew-corrected against the server's own clock rather than trusted at
// face value.
describe('currentUserStore, sessionExpiresAt (system-user hardening)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getCurrentUserMock.mockReset()
    getCurrentSessionMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches the current session only for a system user, and skew-corrects the result', async () => {
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: true }))
    // Server clock is 5s ahead of this client, so the corrected expiry must
    // land on *this* client's timeline, not the server's raw value.
    getCurrentSessionMock.mockResolvedValue({
      expires_at: '2026-08-25T10:15:00.000Z',
      server_time: '2026-08-25T10:00:05.000Z',
    })
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-25T10:00:00.000Z'))

    const store = useCurrentUserStore()
    await store.refresh()

    expect(getCurrentSessionMock).toHaveBeenCalledOnce()
    // expires_at (10:15:00) minus the 5s skew lands at 10:14:55 on this
    // client's clock, i.e. 895s (14:55) from the mocked "now".
    expect(store.sessionExpiresAt).toBe(Date.parse('2026-08-25T10:14:55.000Z'))
  })

  it('leaves the tenant display timezone alone when the user loads', async () => {
    const { getDisplayTimezone, setDisplayTimezone } = await import('@/core/utils/dates')
    setDisplayTimezone('Asia/Tokyo')
    getCurrentUserMock.mockResolvedValue(makeUserResponse())

    await useCurrentUserStore().refresh()

    expect(getDisplayTimezone()).toBe('Asia/Tokyo')
    setDisplayTimezone(null)
  })

  it('does not call getCurrentSession for a non-system user, and leaves sessionExpiresAt null', async () => {
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: false }))

    const store = useCurrentUserStore()
    await store.refresh()

    expect(getCurrentSessionMock).not.toHaveBeenCalled()
    expect(store.sessionExpiresAt).toBeNull()
  })

  it('leaves sessionExpiresAt null, without rejecting refresh(), when the session fetch fails', async () => {
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: true }))
    getCurrentSessionMock.mockRejectedValue(new Error('network error'))

    const store = useCurrentUserStore()
    await expect(store.refresh()).resolves.toBeUndefined()

    expect(store.sessionExpiresAt).toBeNull()
    expect(store.user?.is_systemuser).toBe(true)
  })

  it('clears sessionExpiresAt on logout()', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ is_systemuser: true })
    store.sessionExpiresAt = Date.now() + 900_000

    store.logout()

    expect(store.sessionExpiresAt).toBeNull()
  })

  it('clears sessionExpiresAt on sessionExpired()', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ is_systemuser: true })
    store.sessionExpiresAt = Date.now() + 900_000

    store.sessionExpired()

    expect(store.sessionExpiresAt).toBeNull()
  })
})

// SystemUserWarningDialog's data source: shown once per sign-in, not on
// every plain reload of an already-warned tab (refresh() also runs on
// reload via the router guard). sessionStorage is what tells the two
// apart.
describe('currentUserStore, systemUserWarningPending (once-per-sign-in warning)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getCurrentUserMock.mockReset()
    getCurrentSessionMock.mockReset()
    getCurrentSessionMock.mockResolvedValue({
      expires_at: null,
      server_time: '2026-08-25T10:00:00.000Z',
    })
    sessionStorage.clear()
  })

  it('sets the flag after refresh() for a system user signing in for the first time this tab', async () => {
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: true }))

    const store = useCurrentUserStore()
    await store.refresh()

    expect(store.systemUserWarningPending).toBe(true)
  })

  it('leaves the flag false for a non-system user', async () => {
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: false }))

    const store = useCurrentUserStore()
    await store.refresh()

    expect(store.systemUserWarningPending).toBe(false)
  })

  it('does not set the flag when the sessionStorage key is already present, e.g. a plain reload', async () => {
    sessionStorage.setItem(SYSTEM_USER_WARNING_SESSION_KEY, '1')
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: true }))

    const store = useCurrentUserStore()
    await store.refresh()

    expect(store.systemUserWarningPending).toBe(false)
  })

  it('acknowledgeSystemUserWarning() clears the flag and writes the sessionStorage key', async () => {
    getCurrentUserMock.mockResolvedValue(makeUserResponse({ is_systemuser: true }))
    const store = useCurrentUserStore()
    await store.refresh()
    expect(store.systemUserWarningPending).toBe(true)

    store.acknowledgeSystemUserWarning()

    expect(store.systemUserWarningPending).toBe(false)
    expect(sessionStorage.getItem(SYSTEM_USER_WARNING_SESSION_KEY)).not.toBeNull()
  })

  it('logout() clears both the flag and the sessionStorage key', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ is_systemuser: true })
    store.systemUserWarningPending = true
    sessionStorage.setItem(SYSTEM_USER_WARNING_SESSION_KEY, '1')

    store.logout()

    expect(store.systemUserWarningPending).toBe(false)
    expect(sessionStorage.getItem(SYSTEM_USER_WARNING_SESSION_KEY)).toBeNull()
  })

  it('sessionExpired() clears both the flag and the sessionStorage key', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ is_systemuser: true })
    store.systemUserWarningPending = true
    sessionStorage.setItem(SYSTEM_USER_WARNING_SESSION_KEY, '1')

    store.sessionExpired()

    expect(store.systemUserWarningPending).toBe(false)
    expect(sessionStorage.getItem(SYSTEM_USER_WARNING_SESSION_KEY)).toBeNull()
  })
})

// maintenanceLockout() is sessionExpired()'s sibling: same teardown, same
// "keep the route to return to" query, driven by the api interceptor's
// 503/MaintenanceModeError branch instead of a 401. Exercised with
// storeResetPlugin actually installed (like the suite above), so this
// proves the full reset for real rather than just the local refs.
describe('currentUserStore.maintenanceLockout()', () => {
  beforeEach(() => {
    const pinia = createPinia()
    const app = createApp({})
    app.use(pinia)
    pinia.use(storeResetPlugin)
    setActivePinia(pinia)
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('tears down the session and routes to Login with reason=maintenance, keeping the redirect target', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse()

    store.maintenanceLockout()

    expect(store.user).toBeNull()
    expect(pushMock).toHaveBeenCalledWith({
      name: 'Login',
      query: { reason: 'maintenance', redirect: '/dashboard' },
    })
  })

  it('resets every other store the same way sessionExpired() does', () => {
    const draftStore = useTestDraftStore()
    draftStore.step = 'review'
    draftStore.headers = ['Item']
    const store = useCurrentUserStore()
    store.user = makeUserResponse()

    store.maintenanceLockout()

    expect(draftStore.step).toBe('upload')
    expect(draftStore.headers).toEqual([])
  })

  it('is a no-op when the session is already gone - must tolerate several concurrent failed requests', () => {
    const store = useCurrentUserStore()

    expect(() => store.maintenanceLockout()).not.toThrow()

    expect(pushMock).not.toHaveBeenCalled()
  })

  it('clears sessionExpiresAt, same as sessionExpired()', () => {
    const store = useCurrentUserStore()
    store.user = makeUserResponse({ is_systemuser: true })
    store.sessionExpiresAt = Date.now() + 900_000

    store.maintenanceLockout()

    expect(store.sessionExpiresAt).toBeNull()
  })
})
