import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'

// Same axios and router mocks as LoginView.spec.ts, for the same reasons.
vi.mock('axios', () => {
  const instance = {
    get: vi.fn<() => void>(),
    post: vi.fn<() => void>(),
    put: vi.fn<() => void>(),
    delete: vi.fn<() => void>(),
    interceptors: {
      request: { use: vi.fn<() => void>() },
      response: { use: vi.fn<() => void>() },
    },
    defaults: { headers: { common: {} } },
  }
  return {
    default: {
      get: () => Promise.reject(new Error('not used in this spec')),
      create: () => instance,
      isAxiosError: () => false,
      isCancel: () => false,
    },
  }
})

vi.mock('@/router', () => ({
  default: {
    push: vi.fn<() => void>(),
    currentRoute: { value: { name: 'Login', fullPath: '/login' } },
  },
}))

// jsdom has no WebAuthn; the page is told it may use passkeys but the
// device has no built-in authenticator, so no setup is offered.
vi.mock('../../utils/webauthn', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../utils/webauthn')>()),
  passkeysSupported: () => true,
  platformAuthenticatorAvailable: () => Promise.resolve(false),
}))

import LoginView from '../LoginView.vue'
import { useAuthStore } from '../../stores/authStore'
import { listRememberedUsers, rememberUser } from '../../utils/rememberedUsers'

async function mountLoginView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/login', name: 'Login', component: { template: '<div />' } }],
  })
  await router.push('/login')
  await router.isReady()

  const wrapper = mount(LoginView, {
    global: {
      plugins: [router, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
    },
  })
  await flushPromises()
  return wrapper
}

describe('LoginView, remembered user', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('shows the plain form when nobody signed in on this device', async () => {
    const wrapper = await mountLoginView()

    expect(wrapper.find('#login-username').exists()).toBe(true)
    expect(wrapper.find('[data-testid="login-remembered-user"]').exists()).toBe(false)
  })

  it('offers the remembered user with their name', async () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })

    const wrapper = await mountLoginView()

    expect(wrapper.find('[data-testid="login-remembered-user"]').text()).toContain('Alice Smith')
    expect(wrapper.find('#login-username').exists()).toBe(false)
  })

  it('asks for the password when this device has no passkey for the user', async () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })
    const wrapper = await mountLoginView()
    const loginWithPasskey = vi.spyOn(useAuthStore(), 'loginWithPasskey')

    await wrapper.find('[data-testid="login-chooser-sign-in"]').trigger('click')
    await flushPromises()

    expect(loginWithPasskey).not.toHaveBeenCalled()
    expect(wrapper.find('#login-chooser-password').exists()).toBe(true)
  })

  it('starts the passkey prompt for the passkey this device registered', async () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith', credentialId: 'AQI' })
    const wrapper = await mountLoginView()
    const loginWithPasskey = vi
      .spyOn(useAuthStore(), 'loginWithPasskey')
      .mockResolvedValue('dismissed')

    await wrapper.find('[data-testid="login-chooser-sign-in"]').trigger('click')
    await flushPromises()

    expect(loginWithPasskey).toHaveBeenCalledWith('alice', 'AQI')
    // A dismissed prompt falls back to the password, with a hint.
    expect(wrapper.find('#login-chooser-password').exists()).toBe(true)
    expect(wrapper.text()).toContain(i18n.global.t('login.chooser.usePassword') as string)
  })

  it('switches to the plain form and back', async () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })
    const wrapper = await mountLoginView()

    await wrapper.find('[data-testid="login-switch-user"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('#login-username').exists()).toBe(true)
  })

  it('forgets the user on this device', async () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })
    const wrapper = await mountLoginView()

    await wrapper.find('[data-testid="login-forget-user"]').trigger('click')
    await flushPromises()

    expect(listRememberedUsers()).toEqual([])
    expect(wrapper.find('#login-username').exists()).toBe(true)
  })
})
