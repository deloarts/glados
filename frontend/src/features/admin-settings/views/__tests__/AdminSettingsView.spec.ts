import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

import type { AllAdminSettings } from '../../types/adminSettingsTypes'

const getAllAdminSettingsMock = vi.fn<() => Promise<AllAdminSettings>>()

vi.mock('../../api/getAllAdminSettings', () => ({
  getAllAdminSettings: () => getAllAdminSettingsMock(),
}))

// The tabs are lazy-loaded via the asyncTab helper. Mock every module behind
// a dynamic import so this spec exercises the real tab-strip/routing wiring
// without pulling in each tab's own heavy dependency tree. vi.mock calls must
// stay literal top-level statements (not built in a loop) so Vitest's static
// hoisting can find them.

vi.mock('@/features/admin-settings/components/AdminSettingsTabHost.vue', () =>
  asyncTabStub('AdminSettingsTabHost'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabGeneral.vue', () =>
  asyncTabStub('AdminSettingsTabGeneral'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabUsers.vue', () =>
  asyncTabStub('AdminSettingsTabUsers'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabGroups.vue', () =>
  asyncTabStub('AdminSettingsTabGroups'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabApiKeys.vue', () =>
  asyncTabStub('AdminSettingsTabApiKeys'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabAuth.vue', () =>
  asyncTabStub('AdminSettingsTabAuth'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabMail.vue', () =>
  asyncTabStub('AdminSettingsTabMail'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabStorage.vue', () =>
  asyncTabStub('AdminSettingsTabStorage'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabBackups.vue', () =>
  asyncTabStub('AdminSettingsTabBackups'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabSecurity.vue', () =>
  asyncTabStub('AdminSettingsTabSecurity'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabFeatures.vue', () =>
  asyncTabStub('AdminSettingsTabFeatures'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabNumbering.vue', () =>
  asyncTabStub('AdminSettingsTabNumbering'),
)
vi.mock('@/features/production/components/AdminSettingsTabProduction.vue', () =>
  asyncTabStub('AdminSettingsTabProduction'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabBranding.vue', () =>
  asyncTabStub('AdminSettingsTabBranding'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabNotifications.vue', () =>
  asyncTabStub('AdminSettingsTabNotifications'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabSolidworksPdm.vue', () =>
  asyncTabStub('AdminSettingsTabSolidworksPdm'),
)
vi.mock('@/features/bought-items/components/AdminSettingsTabEplanDataPortal.vue', () =>
  asyncTabStub('AdminSettingsTabEplanDataPortal'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabDataImport.vue', () =>
  asyncTabStub('AdminSettingsTabDataImport'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabStock.vue', () =>
  asyncTabStub('AdminSettingsTabStock'),
)
vi.mock('@/features/time-tracking/components/AdminSettingsTabTimeTracking.vue', () =>
  asyncTabStub('AdminSettingsTabTimeTracking'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabAiModels.vue', () =>
  asyncTabStub('AdminSettingsTabAiModels'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabMaintenance.vue', () =>
  asyncTabStub('AdminSettingsTabMaintenance'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabRetention.vue', () =>
  asyncTabStub('AdminSettingsTabRetention'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabAudit.vue', () =>
  asyncTabStub('AdminSettingsTabAudit'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabSecurityLog.vue', () =>
  asyncTabStub('AdminSettingsTabSecurityLog'),
)
vi.mock('@/features/admin-settings/components/AdminSettingsTabLogs.vue', () =>
  asyncTabStub('AdminSettingsTabLogs'),
)

const TAB_VALUES = [
  'host',
  'general',
  'features',
  'users',
  'groups',
  'apiKeys',
  'auth',
  'mail',
  'storage',
  'backups',
  'security',
  'numbering',
  'production',
  'branding',
  'notifications',
  'solidworks-pdm',
  'eplan-data-portal',
  'data-import',
  'stock-service',
  'time-tracking',
  'aiModels',
  'ai-agents',
  'maintenance',
  'retention',
  'audit',
  'securityLog',
  'agent-calls',
  'logs',
]

import AdminSettingsView from '../AdminSettingsView.vue'

// jsdom does not implement ResizeObserver; OpenVue's TabList binds one in
// its mounted hook to track overflow/scroll buttons.
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/settings/:tab?', name: 'AdminSettings', component: AdminSettingsView }],
  })
  router.push(path)
  return router
}

describe('AdminSettingsView', () => {
  beforeEach(() => {
    getAllAdminSettingsMock.mockReset()
    getAllAdminSettingsMock.mockResolvedValue({} as AllAdminSettings)
  })

  it('fetches the aggregate settings payload on mount, with no arguments', async () => {
    const router = mountAt('/settings/host')
    await router.isReady()

    const wrapper = mountWithApp(AdminSettingsView, { global: { plugins: [router] } })
    await flushPromises()

    expect(getAllAdminSettingsMock).toHaveBeenCalledTimes(1)
    expect(getAllAdminSettingsMock).toHaveBeenCalledWith()

    wrapper.unmount()
  })

  it('renders every tab, in the declared order, and lazy-loads the one from the route', async () => {
    const router = mountAt('/settings/host')
    await router.isReady()

    const wrapper = mountWithApp(AdminSettingsView, { global: { plugins: [router] } })

    const tabs = wrapper.findAllComponents({ name: 'Tab' })
    expect(tabs).toHaveLength(TAB_VALUES.length)
    expect(tabs.map((tab) => tab.props('value'))).toEqual(TAB_VALUES)

    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AdminSettingsTabHost' }).exists()).toBe(true),
    )
    await flushPromises()

    wrapper.unmount()
  })

  it('does not eagerly mount the non-active tabs', async () => {
    const router = mountAt('/settings/host')
    await router.isReady()

    const wrapper = mountWithApp(AdminSettingsView, { global: { plugins: [router] } })

    expect(wrapper.findComponent({ name: 'AdminSettingsTabGeneral' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'AdminSettingsTabUsers' }).exists()).toBe(false)

    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AdminSettingsTabHost' }).exists()).toBe(true),
    )
    expect(wrapper.findComponent({ name: 'AdminSettingsTabGeneral' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('switches to the tab named by the :tab route param, e.g. solidworks-pdm', async () => {
    const router = mountAt('/settings/solidworks-pdm')
    await router.isReady()

    const wrapper = mountWithApp(AdminSettingsView, { global: { plugins: [router] } })

    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AdminSettingsTabSolidworksPdm' }).exists()).toBe(true),
    )
    expect(wrapper.findComponent({ name: 'AdminSettingsTabHost' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('falls back to the host tab for an unknown :tab route param', async () => {
    const router = mountAt('/settings/not-a-real-tab')
    await router.isReady()

    const wrapper = mountWithApp(AdminSettingsView, { global: { plugins: [router] } })

    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AdminSettingsTabHost' }).exists()).toBe(true),
    )

    wrapper.unmount()
  })

  it('updates the route when a different tab is activated', async () => {
    const router = mountAt('/settings/host')
    await router.isReady()

    const wrapper = mountWithApp(AdminSettingsView, { global: { plugins: [router] } })
    await vi.waitFor(() =>
      expect(wrapper.findComponent({ name: 'AdminSettingsTabHost' }).exists()).toBe(true),
    )

    const usersTab = wrapper.findAllComponents({ name: 'Tab' }).find((tab) => tab.props('value') === 'users')!
    await usersTab.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/settings/users')

    wrapper.unmount()
  })
})
