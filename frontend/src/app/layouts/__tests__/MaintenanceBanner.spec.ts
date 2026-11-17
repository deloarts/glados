import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import MaintenanceBanner from '../MaintenanceBanner.vue'

async function mountBanner(permissions: string[] | null = ['write:settings']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (permissions) {
    useCurrentUserStore().user = userWithPermissions(permissions)
  }

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/settings/:tab?', name: 'Settings', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(MaintenanceBanner, { pinia, global: { plugins: [router] } })
  return { wrapper, router }
}

describe('MaintenanceBanner', () => {
  it('renders nothing when hostStore.maintenanceEnabled is false', async () => {
    const { wrapper } = await mountBanner()

    expect(wrapper.find('[data-testid="maintenance-banner"]').exists()).toBe(false)
  })

  it('shows the title and the admin message when maintenance is on', async () => {
    const { wrapper } = await mountBanner()
    useHostStore().maintenanceEnabled = true
    useHostStore().maintenanceMessage = 'Upgrading the database, back shortly.'
    await flushPromises()

    expect(wrapper.text()).toContain('Maintenance mode is on')
    expect(wrapper.text()).toContain('Upgrading the database, back shortly.')
  })

  it('shows no message text when the admin left it blank, but still shows the banner', async () => {
    const { wrapper } = await mountBanner()
    useHostStore().maintenanceEnabled = true
    useHostStore().maintenanceMessage = null
    await flushPromises()

    expect(wrapper.find('[data-testid="maintenance-banner"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Maintenance mode is on')
  })

  it('shows "Open settings" for a user with write:settings', async () => {
    const { wrapper } = await mountBanner(['write:settings'])
    useHostStore().maintenanceEnabled = true
    await flushPromises()

    const link = wrapper.get('.maintenance-banner-link')
    expect(link.attributes('disabled')).toBeUndefined()
  })

  it('disables "Open settings" for a user without write:settings and names the permission', async () => {
    const { wrapper } = await mountBanner([])
    useHostStore().maintenanceEnabled = true
    await flushPromises()

    const link = wrapper.get('.maintenance-banner-link')
    expect(link.attributes('disabled')).toBeDefined()
    const span = link.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Settings.')
  })

  it('hides "Open settings" when nobody is signed in', async () => {
    const { wrapper } = await mountBanner(null)
    useHostStore().maintenanceEnabled = true
    await flushPromises()

    expect(wrapper.find('.maintenance-banner-link').exists()).toBe(false)
  })

  it('navigates to /settings/maintenance when "Open settings" is clicked', async () => {
    const { wrapper, router } = await mountBanner(['write:settings'])
    useHostStore().maintenanceEnabled = true
    await flushPromises()

    await wrapper.find('.maintenance-banner-link').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/settings/maintenance')
  })
})
