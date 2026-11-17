import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.fn<(...args: unknown[]) => void>()
const loginMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const verifyTotpMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const confirmSetupMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()

// A refresh that settles on a later task, like the real network call, so the
// step components re-render away before the store's submit returns.
const refreshMock = vi.fn<() => Promise<void>>(
  () => new Promise<void>((resolve) => setTimeout(resolve, 0)),
)

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({ refresh: refreshMock, user: null }),
}))

vi.mock('@/features/auth/api/login', () => ({
  login: (...a: unknown[]) => loginMock(...a),
  verifyTotp: (...a: unknown[]) => verifyTotpMock(...a),
}))

vi.mock('@/features/auth/api/totp', () => ({
  enrollTotpWithSetupToken: vi
    .fn<() => Promise<unknown>>()
    .mockResolvedValue({ secret: 'JBSWY3DPEHPK3PXP', provisioning_uri: 'otpauth://totp/tester' }),
  confirmTotpWithSetupToken: (...a: unknown[]) => confirmSetupMock(...a),
}))

import LoginView from '../LoginView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

function mountLogin() {
  return mountWithApp(LoginView)
}

async function submitCredentials(wrapper: ReturnType<typeof mountLogin>) {
  await wrapper.find('#login-username').setValue('tester')
  await wrapper.find('input[type="password"]').setValue('secret')
  await wrapper.find('form').trigger('submit.prevent')
  await flushPromises()
}

async function enterCode(wrapper: ReturnType<typeof mountLogin>, code: string) {
  wrapper.findComponent({ name: 'InputOtp' }).vm.$emit('update:modelValue', code)
  await flushPromises()
}

/**
 * An accepted code makes the store drop the step flag before it refreshes the
 * current user, so the step is unmounted by the time the submit settles. The
 * redirect must still happen, which only an F5 used to achieve.
 */
describe('LoginView, second factor redirect', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    verifyTotpMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
    confirmSetupMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
  })

  it('navigates after an accepted two-factor code', async () => {
    loginMock.mockResolvedValue({ totp_required: true, partial_token: 'partial' })
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    await enterCode(wrapper, '123456')

    await vi.waitFor(() => expect(pushMock).toHaveBeenCalledWith('/dashboard'))
  })

  it('stays on the challenge and empties the code after a rejected one', async () => {
    loginMock.mockResolvedValue({ totp_required: true, partial_token: 'partial' })
    verifyTotpMock.mockRejectedValue(new Error('rejected'))
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    await enterCode(wrapper, '000000')

    expect(pushMock).not.toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'InputOtp' }).props('modelValue')).toBe('')
  })

  it('navigates after the forced enrolment accepts its first code', async () => {
    loginMock.mockResolvedValue({
      totp_setup_required: true,
      setup_token: 'setup-tok',
      username: 'tester',
    })
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    await enterCode(wrapper, '123456')

    await vi.waitFor(() => expect(pushMock).toHaveBeenCalledWith('/dashboard'))
  })
})
