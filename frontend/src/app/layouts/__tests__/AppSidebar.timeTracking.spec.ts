import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { UserResponse } from '@/core/types/userResponse'
import type { TimeTrackingAccountResponse } from '@/features/time-tracking'

vi.mock('@/core/api/users/updateUser', () => ({
  updateUser: vi.fn<() => Promise<unknown>>(),
}))

const getAccountMock = vi.fn<() => Promise<TimeTrackingAccountResponse>>()
const getMonthMock = vi.fn<(month: string) => Promise<unknown>>()
const getYearMock = vi.fn<(year: number) => Promise<unknown>>()
const checkAccessMock = vi.fn<() => Promise<unknown>>()

vi.mock('@/features/time-tracking/api/timeTrackingApi', () => ({
  getMyTimeTrackingAccount: () => getAccountMock(),
  saveMyTimeTrackingAccount: vi.fn<() => Promise<unknown>>(),
  deleteMyTimeTrackingAccount: vi.fn<() => Promise<void>>(),
  checkMyTimeTrackingAccess: () => checkAccessMock(),
  getMyTimeTrackingMonth: (month: string) => getMonthMock(month),
  getMyTimeTrackingYear: (year: number) => getYearMock(year),
}))

import AppSidebar from '../AppSidebar.vue'

function makeAccount(overrides: Partial<TimeTrackingAccountResponse> = {}): TimeTrackingAccountResponse {
  return {
    time_tracking_user: 'jdoe',
    time_tracking_password_configured: true,
    time_tracking_credentials_valid: true,
    time_tracking_credentials_invalid_reason: null,
    time_tracking_consent_version: 1,
    time_tracking_consent_current: true,
    time_tracking_privacy_policy_url: null,
    time_tracking_provider_label: 'Example Time',
    time_tracking_employee_name: null,
    time_tracking_rights: null,
    ...overrides,
  }
}

interface Setup {
  enabled: boolean
  shared?: boolean
  account?: TimeTrackingAccountResponse
  path?: string
}

async function mountSidebar(setup: Setup) {
  setActivePinia(createPinia())
  const hostStore = useHostStore()
  hostStore.timeTrackingEnabled = setup.enabled
  hostStore.timeTrackingProviderLabel = setup.enabled ? 'Example Time' : null
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: setup.shared ?? false,
    permissions: [],
  } as unknown as UserResponse
  getAccountMock.mockResolvedValue(setup.account ?? makeAccount())

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push(setup.path ?? '/')

  const wrapper = mount(AppSidebar, {
    props: { collapsed: false },
    global: { plugins: [router, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n] },
  })
  await flushPromises()
  return wrapper
}

describe('AppSidebar, time tracking shortcut', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('links to the Time Tracking tab for a personal account with usable credentials', async () => {
    const wrapper = await mountSidebar({ enabled: true })

    const item = wrapper.find('[data-testid="nav-time-tracking"]')
    expect(item.exists()).toBe(true)
    expect(item.attributes('href')).toBe('/account/time-tracking')

    wrapper.unmount()
  })

  it('reads only the account state on app load, never the time tracking data', async () => {
    const wrapper = await mountSidebar({ enabled: true })

    expect(getAccountMock).toHaveBeenCalledTimes(1)
    expect(getMonthMock).not.toHaveBeenCalled()
    expect(getYearMock).not.toHaveBeenCalled()
    expect(checkAccessMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('is hidden, without any request, while time tracking is off', async () => {
    const wrapper = await mountSidebar({ enabled: false })

    expect(wrapper.find('[data-testid="nav-time-tracking"]').exists()).toBe(false)
    expect(getAccountMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('is hidden for a shared account', async () => {
    const wrapper = await mountSidebar({ enabled: true, shared: true })

    expect(wrapper.find('[data-testid="nav-time-tracking"]').exists()).toBe(false)
    expect(getAccountMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('is hidden while the stored credentials are not usable', async () => {
    const wrapper = await mountSidebar({
      enabled: true,
      account: makeAccount({
        time_tracking_credentials_valid: false,
        time_tracking_credentials_invalid_reason: 'auth_failed',
      }),
    })

    expect(wrapper.find('[data-testid="nav-time-tracking"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('is active on the Time Tracking tab', async () => {
    const wrapper = await mountSidebar({ enabled: true, path: '/account/time-tracking' })

    expect(wrapper.find('[data-testid="nav-time-tracking"]').classes()).toContain('active')

    wrapper.unmount()
  })
})
