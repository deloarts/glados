import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


const pushMock = vi.fn<(...args: unknown[]) => void>()
const loginMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({ refresh: vi.fn<() => Promise<void>>() }),
}))

vi.mock('@/features/auth/api/login', () => ({
  login: (...a: unknown[]) => loginMock(...a),
  verifyTotp: vi.fn<() => Promise<unknown>>(),
}))

vi.mock('@/features/auth/api/totp', () => ({
  enrollTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
  confirmTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
}))

import LoginView from '../LoginView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

function mountLogin() {
  return mountWithApp(LoginView)
}

// The backend answers an empty username/password with a 422 (missing
// form field) rather than the 401 a real wrong-credentials guess gets, and
// that 422 has no friendly mapping in authStore, so the guard has to stop
// the request from ever leaving the browser.
describe('LoginView, empty-credentials submit', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loginMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
  })

  it('disables the submit button while the password is empty', async () => {
    const wrapper = mountLogin()
    await wrapper.find('#login-username').setValue('tester')

    const button = wrapper.find('button[type="submit"]')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('does not call login when the form is submitted with an empty password', async () => {
    const wrapper = mountLogin()
    await wrapper.find('#login-username').setValue('tester')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(loginMock).not.toHaveBeenCalled()
  })

  it('does not call login when the form is submitted with an empty username', async () => {
    const wrapper = mountLogin()
    await wrapper.find('input[type="password"]').setValue('secret')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(loginMock).not.toHaveBeenCalled()
  })

  it('calls login once both fields are filled', async () => {
    const wrapper = mountLogin()
    await wrapper.find('#login-username').setValue('tester')
    await wrapper.find('input[type="password"]').setValue('secret')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(loginMock).toHaveBeenCalledWith({ username: 'tester', password: 'secret' })
  })
})
