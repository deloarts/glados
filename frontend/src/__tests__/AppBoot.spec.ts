import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import axios from 'axios'

import { i18n } from '@/core/i18n'
import { useLayoutStore } from '@/core/stores/layoutStore'
import {
  forgetShownScreenLanguage,
  updateDeviceScreenMemory,
} from '@/core/terminal/deviceScreenMemory'
import { RouteStub } from '@/test-utils/factories'
import { mountWithApp } from '@/test-utils/mountWithApp'

vi.mock('@/core/api', () => ({
  default: { get: vi.fn<(url: string) => Promise<unknown>>(() => Promise.resolve({ data: {} })) },
}))

import App from '../App.vue'

// How the app boots on a wall display: nothing of the app shell before the
// first route has resolved, and the screen theme and language the display
// remembers applied before anything is rendered.
const STUBS = {
  AppLayout: { template: '<div data-testid="app-layout" />' },
  AuthLayout: { template: '<div data-testid="auth-layout" />' },
  KioskLayout: { template: '<div data-testid="kiosk-layout" />' },
  LiveConnectionHandler: true,
  AnnouncementsHandler: true,
  ToastHandler: true,
}

// A router opened at the given address, which App.vue's install of the
// router navigates to on mount, as in the browser.
function routerAt(path: string) {
  const history = createMemoryHistory()
  history.replace(path)
  return createRouter({
    history,
    routes: [
      { path: '/infoscreen', component: RouteStub, meta: { requiresAuth: false, layout: 'kiosk' } },
      { path: '/resources', component: RouteStub },
    ],
  })
}

function mountAt(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = routerAt(path)
  const wrapper = mountWithApp(App, { pinia, global: { plugins: [router], stubs: STUBS } })
  return { wrapper, router }
}

describe('App boot', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('p-dark')
    // The public branding store reads through plain axios, which the module
    // mock above does not cover. Unmocked, jsdom sends a real request to its
    // own origin, http://localhost:3000, where a running dev backend answers
    // after the test has ended and sets its tenant default in a later test.
    vi.spyOn(axios, 'get').mockResolvedValue({ data: { app_name: 'Glados', default_language: 'enGB' } })
  })

  afterEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('p-dark')
    forgetShownScreenLanguage()
    i18n.global.locale.value = 'enGB'
  })

  it('renders no layout before the first route resolves and the kiosk layout after', async () => {
    const { wrapper } = mountAt('/infoscreen')

    expect(wrapper.find('[data-testid="app-layout"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="kiosk-layout"]').exists()).toBe(false)

    await flushPromises()

    expect(wrapper.find('[data-testid="kiosk-layout"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="app-layout"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders the app layout once a normal route has resolved', async () => {
    const { wrapper } = mountAt('/resources')
    expect(wrapper.find('[data-testid="app-layout"]').exists()).toBe(false)

    await flushPromises()

    expect(wrapper.find('[data-testid="app-layout"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('paints the remembered screen theme on a device before the first render and keeps it', async () => {
    updateDeviceScreenMemory({
      theme: { color_mode: 'dark', theme_preset: 'Nora', primary_color: 'emerald' },
    })

    const { wrapper } = mountAt('/infoscreen')

    // Already dark while nothing is rendered yet; matchMedia is stubbed to
    // light, so the boot default would have painted it light.
    expect(wrapper.find('[data-testid="kiosk-layout"]').exists()).toBe(false)
    expect(document.documentElement.classList.contains('p-dark')).toBe(true)

    await flushPromises()

    expect(document.documentElement.classList.contains('p-dark')).toBe(true)
    expect(useLayoutStore().isDarkMode).toBe(true)
    wrapper.unmount()
  })

  it('leaves the remembered screen theme alone outside the device routes', async () => {
    updateDeviceScreenMemory({
      theme: { color_mode: 'dark', theme_preset: 'Nora', primary_color: 'emerald' },
    })

    const { wrapper } = mountAt('/resources')
    await flushPromises()

    expect(document.documentElement.classList.contains('p-dark')).toBe(false)
    wrapper.unmount()
  })

  it('starts a device in the remembered language and keeps it over the tenant default', async () => {
    updateDeviceScreenMemory({ language: 'deAT' })
    // The public branding answers with the tenant default for visitors.
    vi.spyOn(axios, 'get').mockResolvedValue({ data: { app_name: 'Glados', default_language: 'enGB' } })

    const { wrapper } = mountAt('/infoscreen')
    expect(i18n.global.locale.value).toBe('deAT')

    await flushPromises()

    expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/api/v1/public/branding'))
    expect(i18n.global.locale.value).toBe('deAT')
    wrapper.unmount()
  })

  it('starts a device without a remembered language in the tenant default', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({ data: { app_name: 'Glados', default_language: 'deAT' } })

    const { wrapper } = mountAt('/infoscreen')
    await flushPromises()

    expect(i18n.global.locale.value).toBe('deAT')
    wrapper.unmount()
  })

  it('leaves the remembered language alone outside the device routes', async () => {
    updateDeviceScreenMemory({ language: 'deAT' })

    const { wrapper } = mountAt('/resources')
    await flushPromises()

    expect(i18n.global.locale.value).toBe('enGB')
    wrapper.unmount()
  })
})
