import { describe, it, expect, vi, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import router from '@/router'

// No session cookie: the router guard's one-off session probe gets a 401,
// every other request resolves empty.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>((url) =>
      url === '/users/me'
        ? Promise.reject(Object.assign(new Error('Unauthorized'), { response: { status: 401 } }))
        : Promise.resolve({ data: {} }),
    ),
  },
}))

import App from '../App.vue'
import { useEasterEggs } from '@/core/composables/useEasterEggs'

describe('App', () => {
  it('redirects an unauthenticated user to the login view', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    // Navigate to a registered route (not '/', which redirects to the
    // currently-unregistered '/dashboard', see router/index.ts).
    await router.push('/resources')
    await router.isReady()

    const wrapper = mountWithApp(App, {
      pinia,
      global: {
        plugins: [router],
      },
    })

    await flushPromises()

    expect(router.currentRoute.value.name).toBe('Login')
    expect(wrapper.find('#login-username').exists()).toBe(true)

    wrapper.unmount()
  })
})

// Aperture mode is a dark-room affair: the Konami code has to bring dark mode
// with it, and hand the user's own preference back when it is switched off.
// The mode's state is a module singleton, so it is reset between tests.
describe('App, aperture mode dark mode', () => {
  afterEach(() => {
    useEasterEggs().setAperture(false)
    document.documentElement.classList.remove('p-dark')
  })

  async function mountApp() {
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/resources')
    await router.isReady()

    const wrapper = mountWithApp(App, {
      pinia,
      global: {
        plugins: [router],
      },
    })
    await flushPromises()
    return wrapper
  }

  it('switches to dark mode when aperture mode is turned on', async () => {
    const wrapper = await mountApp()
    // matchMedia is stubbed to matches:false, so the boot default is light.
    expect(document.documentElement.classList.contains('p-dark')).toBe(false)

    useEasterEggs().setAperture(true)
    await nextTick()

    expect(document.documentElement.classList.contains('p-dark')).toBe(true)

    wrapper.unmount()
  })

  it('falls back to the OS preference when aperture mode is turned off', async () => {
    const wrapper = await mountApp()

    useEasterEggs().setAperture(true)
    await nextTick()
    useEasterEggs().setAperture(false)
    await nextTick()

    expect(document.documentElement.classList.contains('p-dark')).toBe(false)

    wrapper.unmount()
  })
})
