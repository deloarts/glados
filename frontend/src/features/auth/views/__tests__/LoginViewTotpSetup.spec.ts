import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


const pushMock = vi.fn<(...args: unknown[]) => void>()
const loginMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const enrollMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()

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
  enrollTotpWithSetupToken: (...a: unknown[]) => enrollMock(...a),
  confirmTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
}))

import LoginView from '../LoginView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

/**
 * The forced-2FA step is rendered by LoginView itself, so the store tests
 * cannot see it. This mounts the real component and drives a login that
 * returns the setup challenge.
 *
 * onSubmit must not navigate merely because `totpRequired` is false, which
 * is also true during forced enrolment: that would push away from the login
 * page mid-flow, bounce off the router guard (no session yet) and leave the
 * user staring at a step with no QR code and no secret.
 */
function mountLogin() {
  return mountWithApp(LoginView)
}

async function submitCredentials(wrapper: ReturnType<typeof mountLogin>) {
  await wrapper.find('#login-username').setValue('tester')
  // An empty password never submits (see LoginView's canSubmit guard), so
  // this needs a real one to reach login().
  await wrapper.find('input[type="password"]').setValue('secret')
  await wrapper.find('form').trigger('submit.prevent')
  await flushPromises()
}

/**
 * QR generation encodes a PNG, which microtask flushing alone does not
 * resolve, wait for the image to actually appear.
 */
async function submitAndAwaitQr(wrapper: ReturnType<typeof mountLogin>) {
  await submitCredentials(wrapper)
  await vi.waitFor(() => {
    if (!wrapper.find('img.totp-qr').exists()) throw new Error('QR not rendered yet')
  })
}

describe('LoginView, forced 2FA enrolment', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    loginMock.mockResolvedValue({
      totp_setup_required: true,
      setup_token: 'setup-tok',
      username: 'tester',
    })
    enrollMock.mockResolvedValue({
      secret: 'JBSWY3DPEHPK3PXP',
      provisioning_uri: 'otpauth://totp/tester?secret=JBSWY3DPEHPK3PXP&issuer=Glados',
    })
  })

  it('shows the QR code', async () => {
    const wrapper = mountLogin()
    await submitAndAwaitQr(wrapper)

    const img = wrapper.find('img.totp-qr')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toMatch(/^data:image\/png;base64,/)
  })

  it('shows the secret for manual entry', async () => {
    const wrapper = mountLogin()
    await submitAndAwaitQr(wrapper)

    expect(wrapper.find('.totp-secret').text()).toContain('JBSWY3DPEHPK3PXP')
  })

  it('does not navigate away from the login page', async () => {
    const wrapper = mountLogin()
    await submitAndAwaitQr(wrapper)

    expect(pushMock).not.toHaveBeenCalled()
  })

  it('replaces the credentials form with the enrolment step', async () => {
    const wrapper = mountLogin()
    await submitAndAwaitQr(wrapper)

    expect(wrapper.find('#login-password').exists()).toBe(false)
  })

  it('copies the secret to the clipboard', async () => {
    const writeText = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mountLogin()
    await submitAndAwaitQr(wrapper)
    await wrapper.find('.totp-secret-copy').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('JBSWY3DPEHPK3PXP')
  })

  it('confirms on the button after copying', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn<() => Promise<void>>().mockResolvedValue(undefined) },
    })

    const wrapper = mountLogin()
    await submitAndAwaitQr(wrapper)
    expect(wrapper.find('.totp-secret-copy').classes()).not.toContain('is-copied')

    await wrapper.find('.totp-secret-copy').trigger('click')
    await flushPromises()

    expect(wrapper.find('.totp-secret-copy').classes()).toContain('is-copied')
  })

  it('still navigates for an ordinary login', async () => {
    loginMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })

    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalled()
  })
})
