import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import InputOtp from 'openvue/inputotp'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'

const enrollTotpMock =
  vi.fn<(password: string) => Promise<{ secret: string; provisioning_uri: string }>>()
const confirmTotpMock = vi.fn<(code: string) => Promise<void>>()
const disableTotpMock = vi.fn<(code: string) => Promise<void>>()

vi.mock('../../api/totp', () => ({
  enrollTotp: (password: string) => enrollTotpMock(password),
  confirmTotp: (code: string) => confirmTotpMock(code),
  disableTotp: (code: string) => disableTotpMock(code),
  enrollTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
  confirmTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
}))

import TwoFactorView from '../TwoFactorView.vue'

// axios.isAxiosError() only requires the `isAxiosError` marker. See the
// same pattern already used in authStore.spec.ts.
function axiosError(code: string) {
  return { isAxiosError: true, response: { status: 401, data: { code } } }
}

function mountView() {
  return mountWithApp(TwoFactorView)
}

/** Opens the setup and submits `password` in its password step. */
async function openSetupWithPassword(wrapper: ReturnType<typeof mountView>, password: string) {
  await wrapper.find('button').trigger('click') // "Enable 2FA"
  await wrapper.find('input[type="password"]').setValue(password)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

describe('TwoFactorView, error code handling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('confirming enrolment', () => {
    async function startEnrolAndSubmit(code: string) {
      enrollTotpMock.mockResolvedValue({
        secret: 'JBSWY3DPEHPK3PXP',
        provisioning_uri: 'otpauth://totp/x',
      })
      const wrapper = mountView()
      await openSetupWithPassword(wrapper, 'my-password')

      // QRCode.toDataURL is real (unmocked) and async beyond a single
      // microtask flush, so wait for the image it produces, same pattern as
      // LoginViewTotpSetup.spec.ts's submitAndAwaitQr.
      await vi.waitFor(() => {
        if (!wrapper.find('img.qr-code').exists()) throw new Error('QR not rendered yet')
      })

      const otp = wrapper.findComponent(InputOtp)
      await otp.vm.$emit('update:model-value', code)
      await flushPromises()
      return wrapper
    }

    it('shows "invalid code" for InvalidTOTPCodeError', async () => {
      confirmTotpMock.mockRejectedValue(axiosError('InvalidTOTPCodeError'))
      const wrapper = await startEnrolAndSubmit('000000')

      expect(wrapper.text()).toContain('Invalid code. Please try again.')
    })

    it('shows a generic error for anything else', async () => {
      confirmTotpMock.mockRejectedValue(axiosError('SomeOtherError'))
      const wrapper = await startEnrolAndSubmit('000000')

      expect(wrapper.text()).toContain('Something went wrong. Please try again.')
    })
  })

  describe('confirming the password', () => {
    it('sends the password and shows the QR code', async () => {
      enrollTotpMock.mockResolvedValue({
        secret: 'JBSWY3DPEHPK3PXP',
        provisioning_uri: 'otpauth://totp/x',
      })
      const wrapper = mountView()
      await openSetupWithPassword(wrapper, 'my-password')

      expect(enrollTotpMock).toHaveBeenCalledWith('my-password')
      await vi.waitFor(() => {
        if (!wrapper.find('img.qr-code').exists()) throw new Error('QR not rendered yet')
      })
    })

    it('shows "wrong password" for PasswordConfirmationFailedError', async () => {
      enrollTotpMock.mockRejectedValue(axiosError('PasswordConfirmationFailedError'))
      const wrapper = mountView()
      await openSetupWithPassword(wrapper, 'wrong')

      expect(wrapper.text()).toContain('The password is not correct.')
      expect(wrapper.find('img.qr-code').exists()).toBe(false)
    })
  })

  describe('disabling 2FA', () => {
    function mountEnabled() {
      const wrapper = mountView()
      useCurrentUserStore().user = { totp_enabled: true } as unknown as UserResponse
      return wrapper
    }

    async function openDisableAndSubmit(code: string) {
      const wrapper = mountEnabled()
      await wrapper.vm.$nextTick()
      await wrapper.find('button').trigger('click') // "Disable 2FA"
      await flushPromises()

      const otp = wrapper.findComponent(InputOtp)
      await otp.vm.$emit('update:model-value', code)
      await flushPromises()
      return wrapper
    }

    it('shows "invalid code" for InvalidTOTPCodeError', async () => {
      disableTotpMock.mockRejectedValue(axiosError('InvalidTOTPCodeError'))
      const wrapper = await openDisableAndSubmit('000000')

      expect(wrapper.text()).toContain('Invalid code. Please try again.')
    })

    it('shows a generic error for anything else', async () => {
      disableTotpMock.mockRejectedValue(axiosError('SomeOtherError'))
      const wrapper = await openDisableAndSubmit('000000')

      expect(wrapper.text()).toContain('Something went wrong. Please try again.')
    })
  })
})
