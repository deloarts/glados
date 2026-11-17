import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'

// Same lazy-tab stubbing as AccountView.spec.ts, plus the Time Tracking
// view, so only the tab strip and its visibility rules are exercised.
vi.mock('../AccountMeView.vue', () => asyncTabStub('AccountMeView', '<div>me-stub</div>'))
vi.mock('@/features/time-tracking/views/AccountTimeTrackingView.vue', () => asyncTabStub('AccountTimeTrackingView', '<div>time-tracking-stub</div>'))
vi.mock('../AccountNotificationsView.vue', () => asyncTabStub('AccountNotificationsView', '<div>notifications-stub</div>'))
vi.mock('../AccountAccessTokenView.vue', () => asyncTabStub('AccountAccessTokenView', '<div>pat-stub</div>'))
vi.mock('@/features/auth/views/TwoFactorView.vue', () => asyncTabStub('TwoFactorView', '<div>2fa-stub</div>'))
vi.mock('../AccountSessionsView.vue', () => asyncTabStub('AccountSessionsView', '<div>sessions-stub</div>'))
vi.mock('../AccountPermissionsView.vue', () => asyncTabStub('AccountPermissionsView', '<div>permissions-stub</div>'))

import AccountView from '../AccountView.vue'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

interface Setup {
  enabled: boolean
  shared?: boolean
  systemUser?: boolean
  hostLoaded?: boolean
}

async function mountAt(path: string, setup: Setup) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const hostStore = useHostStore()
  hostStore.timeTrackingEnabled = setup.enabled
  hostStore.timeTrackingProviderLabel = setup.enabled ? 'Example Time' : null
  hostStore.loaded = setup.hostLoaded ?? true
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: setup.systemUser ?? false,
    is_shared_account: setup.shared ?? false,
    permissions: [],
  } as unknown as UserResponse

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/account/:tab?', name: 'Account', component: AccountView }],
  })
  router.push(path)
  await router.isReady()

  const wrapper = mountWithApp(AccountView, { pinia, global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

function tabValues(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper']): string[] {
  return wrapper.findAllComponents({ name: 'Tab' }).map((tab) => tab.props('value') as string)
}

describe('AccountView, time tracking tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sits between My Account and Notifications for a personal account', async () => {
    const { wrapper } = await mountAt('/account/me', { enabled: true })

    expect(tabValues(wrapper).slice(0, 3)).toEqual(['me', 'time-tracking', 'notifications'])
    expect(wrapper.text()).toContain('Time Tracking')

    wrapper.unmount()
  })

  it('is hidden while time tracking is off', async () => {
    const { wrapper } = await mountAt('/account/me', { enabled: false })

    expect(tabValues(wrapper)).not.toContain('time-tracking')

    wrapper.unmount()
  })

  it('is hidden for a shared account and for the system user', async () => {
    const shared = await mountAt('/account/me', { enabled: true, shared: true })
    expect(tabValues(shared.wrapper)).not.toContain('time-tracking')
    shared.wrapper.unmount()

    const system = await mountAt('/account/me', { enabled: true, systemUser: true })
    expect(tabValues(system.wrapper)).not.toContain('time-tracking')
    system.wrapper.unmount()
  })

  it('opens the tab from the route', async () => {
    const { wrapper } = await mountAt('/account/time-tracking', { enabled: true })

    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AccountTimeTrackingView' }).exists()).toBe(true),
    )

    wrapper.unmount()
  })

  it('falls back to My Account for the tab route once time tracking turns out to be off', async () => {
    const { wrapper, router } = await mountAt('/account/time-tracking', {
      enabled: false,
      hostLoaded: false,
    })

    useHostStore().loaded = true
    await flushPromises()

    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AccountMeView' }).exists()).toBe(true),
    )
    expect(router.currentRoute.value.path).toBe('/account/me')

    wrapper.unmount()
  })
})
