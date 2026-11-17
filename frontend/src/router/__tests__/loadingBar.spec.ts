import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({
    user: null,
    loading: false,
    sessionChecked: true,
    isAdmin: false,
    refresh: vi.fn<() => Promise<void>>(),
  }),
}))

vi.mock('@/core/host/stores/hostStore', () => ({
  useHostStore: () => ({ fetch: vi.fn<() => Promise<void>>() }),
}))

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginView', template: '<div />' },
}))

import router from '@/router'
import { useLoadingBarStore } from '@/core/stores/loadingBarStore'

describe('router loading bar integration', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('releases the bar when a guard redirects the navigation', async () => {
    const loadingBarStore = useLoadingBarStore()

    // Unauthenticated: the guard redirects to Login, which makes vue-router
    // restart the navigation: `beforeEach` runs twice, `afterEach` only once.
    await router.push('/dashboard')
    expect(router.currentRoute.value.name).toBe('Login')

    vi.advanceTimersByTime(5000)
    expect(loadingBarStore.isLoading).toBe(false)
  })

  it('does not release another consumer’s bar on a duplicated navigation', async () => {
    const loadingBarStore = useLoadingBarStore()

    await router.push('/login')
    vi.advanceTimersByTime(5000)

    // Something else (a table fetch) owns the bar.
    loadingBarStore.start()
    expect(loadingBarStore.isLoading).toBe(true)

    // A duplicated navigation fires `afterEach` without ever running the guards.
    await router.push('/login')
    vi.advanceTimersByTime(5000)
    expect(loadingBarStore.isLoading).toBe(true)

    loadingBarStore.stop()
    vi.advanceTimersByTime(5000)
    expect(loadingBarStore.isLoading).toBe(false)
  })
})
