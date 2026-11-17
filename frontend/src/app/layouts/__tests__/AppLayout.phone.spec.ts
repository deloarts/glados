import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import AppLayout from '../AppLayout.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubPhoneScreen } from '@/test-utils/phoneScreen'

// Same stand-in as AppLayout.spec.ts: the real dialog pulls in most features.
vi.mock('@/features/production/lots/components/LotDetailDialog.vue', () => ({
  default: { name: 'LotDetailDialog', render: () => null },
}))
vi.mock('@/features/scan/components/ScanDialog.vue', () => ({
  default: { name: 'ScanDialog', render: () => null },
}))

const Page = { template: '<div data-testid="page" />' }

async function mountLayout(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/dashboard', name: 'Dashboard', component: Page, meta: { phone: true } },
      { path: '/settings', name: 'Settings', component: Page },
    ],
  })
  await router.push(path)
  await router.isReady()

  const wrapper = mountWithApp(AppLayout, {
    pinia,
    global: {
      plugins: [router],
      stubs: {
        AppSidebar: true,
        AppHeader: true,
        AppFooter: true,
        AppBottomNav: true,
        LotDetailDialog: true,
        ScanDialog: true,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('AppLayout on a phone', () => {
  let unmount: (() => void) | null = null

  beforeEach(() => {
    stubPhoneScreen(true)
  })

  afterEach(() => {
    unmount?.()
    unmount = null
  })

  it('shows a desktop page as a notice until the user asks for it anyway', async () => {
    const { wrapper } = await mountLayout('/settings')
    unmount = () => wrapper.unmount()

    expect(wrapper.find('[data-testid="desktop-only-notice"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="page"]').exists()).toBe(false)

    await wrapper.find('[data-testid="desktop-only-show-anyway"]').trigger('click')

    expect(wrapper.find('[data-testid="desktop-only-notice"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="page"]').exists()).toBe(true)
  })

  it('renders a phone page directly, with the bottom navigation instead of the footer', async () => {
    const { wrapper } = await mountLayout('/dashboard')
    unmount = () => wrapper.unmount()

    expect(wrapper.find('[data-testid="page"]').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AppBottomNav' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AppFooter' }).exists()).toBe(false)
  })

  it('marks the page area for the phone columns while phone mode is on', async () => {
    const { wrapper } = await mountLayout('/settings')
    unmount = () => wrapper.unmount()

    expect(wrapper.get('#main-content').classes()).toContain('phone-mode')

    await wrapper.find('[data-testid="desktop-only-show-anyway"]').trigger('click')

    expect(wrapper.get('#main-content').classes()).not.toContain('phone-mode')
  })
})

describe('AppLayout on a desktop', () => {
  it('renders every page with the footer and no bottom navigation', async () => {
    stubPhoneScreen(false)
    const { wrapper } = await mountLayout('/settings')

    expect(wrapper.find('[data-testid="page"]').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AppFooter' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AppBottomNav' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
