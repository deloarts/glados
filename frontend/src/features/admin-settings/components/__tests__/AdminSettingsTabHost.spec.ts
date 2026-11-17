import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import type {
  AllAdminSettings,
  HostStats,
  IntegrationsOverview,
  ServicesHealth,
} from '../../types/adminSettingsTypes'

const getMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
  },
}))

import AdminSettingsTabHost from '../AdminSettingsTabHost.vue'

function makeHostStats(overrides: Partial<HostStats> = {}): HostStats {
  return {
    domain: 'example.local',
    hostname: 'host-1',
    platform: 'Linux',
    python_version: '3.13.0',
    app_version: '1.0.0',
    boot_time: '2026-08-01T00:00:00Z',
    process_start_time: '2026-08-01T00:00:00Z',
    cpu_count: 4,
    cpu_percent: 10,
    memory_total_bytes: 2048,
    memory_used_bytes: 1536,
    memory_percent: 50,
    disk_total_bytes: 2048,
    disk_used_bytes: 1536,
    disk_percent: 50,
    ...overrides,
  }
}

function makeServicesHealth(): ServicesHealth {
  return { services: [] }
}

async function mountTab() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mountWithApp(AdminSettingsTabHost, { pinia })
  await flushPromises()
  return wrapper
}

describe('AdminSettingsTabHost - memory/disk byte formatting', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/admin/settings/host/stats') return Promise.resolve({ data: makeHostStats() })
      return Promise.resolve({ data: makeServicesHealth() })
    })
  })

  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  // 1536 bytes total, sitting right at 1.5 KiB, is small enough that
  // formatBytes keeps one fraction digit, the case a bare `.toFixed(1)`
  // would render in the browser's own language rather than the UI
  // language picked in Glados.
  it('renders the memory usage with a period decimal separator for en-GB', async () => {
    const wrapper = await mountTab()

    expect(wrapper.text()).toContain('1.5 KiB / 2.0 KiB')

    wrapper.unmount()
  })

  it('renders the memory usage with a comma decimal separator for de-AT', async () => {
    i18n.global.locale.value = 'deAT'
    const wrapper = await mountTab()

    expect(wrapper.text()).toContain('1,5 KiB / 2,0 KiB')

    wrapper.unmount()
  })
})

describe('AdminSettingsTabHost - at a glance', () => {
  const integrations: IntegrationsOverview = {
    integrations: [
      { key: 'mail', state: 'active' },
      { key: 'pdm', state: 'incomplete' },
      { key: 'ldap', state: 'off' },
    ],
  }

  beforeEach(() => {
    getMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/admin/settings/host/stats') return Promise.resolve({ data: makeHostStats() })
      if (url === '/admin/settings/host/integrations') return Promise.resolve({ data: integrations })
      return Promise.resolve({ data: makeServicesHealth() })
    })
  })

  async function mountWithRouter() {
    const pinia = createPinia()
    setActivePinia(pinia)
    useAdminSettingsStore().settings = {
      features: { enable_production_planning: true, enable_calculations: false },
    } as unknown as AllAdminSettings
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/settings/:tab?', component: { template: '<div />' } }],
    })
    await router.push('/settings/host')
    const wrapper = mountWithApp(AdminSettingsTabHost, { pinia, global: { plugins: [router] } })
    await flushPromises()
    return { wrapper, router }
  }

  it('shows each integration with its state', async () => {
    const { wrapper } = await mountWithRouter()

    expect(wrapper.find('[data-testid="integration-mail"]').text()).toContain('Active')
    expect(wrapper.find('[data-testid="integration-pdm"]').text()).toContain('Not configured')
    expect(wrapper.find('[data-testid="integration-ldap"]').text()).toContain('Off')

    wrapper.unmount()
  })

  it('opens the settings tab of an integration', async () => {
    const { wrapper, router } = await mountWithRouter()

    await wrapper.find('[data-testid="integration-pdm"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/settings/solidworks-pdm')

    wrapper.unmount()
  })

  it('shows the module switches from the feature settings', async () => {
    const { wrapper } = await mountWithRouter()

    expect(wrapper.find('[data-testid="module-enable_production_planning"]').text()).toContain('On')
    expect(wrapper.find('[data-testid="module-enable_calculations"]').text()).toContain('Off')

    wrapper.unmount()
  })
})
