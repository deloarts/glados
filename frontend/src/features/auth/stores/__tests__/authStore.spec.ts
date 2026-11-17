import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const loginMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const verifyTotpMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const enrollMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const confirmMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
const refreshMock = vi.fn<() => Promise<void>>()

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({ refresh: refreshMock }),
}))

vi.mock('../../api/login', () => ({
  login: (...args: unknown[]) => loginMock(...args),
  verifyTotp: (...args: unknown[]) => verifyTotpMock(...args),
}))

vi.mock('../../api/totp', () => ({
  enrollTotpWithSetupToken: (...args: unknown[]) => enrollMock(...args),
  confirmTotpWithSetupToken: (...args: unknown[]) => confirmMock(...args),
}))

import { useAuthStore } from '../authStore'

const CREDENTIALS = { username: 'tester', password: 'pw' }

describe('authStore.login', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    enrollMock.mockResolvedValue({ secret: 'S3CR3T', provisioning_uri: 'otpauth://x' })
  })

  it('signs the user in via the session cookie for an ordinary login', async () => {
    loginMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })

    await useAuthStore().login(CREDENTIALS)

    // The session cookie the response sets is what actually authenticates
    // the user, refresh() is what confirms it by loading /users/me.
    expect(refreshMock).toHaveBeenCalledOnce()
  })

  it('branches to the 2FA challenge without signing the user in', async () => {
    loginMock.mockResolvedValue({ totp_required: true, partial_token: 'partial' })

    const store = useAuthStore()
    await store.login(CREDENTIALS)

    expect(store.totpRequired).toBe(true)
    expect(refreshMock).not.toHaveBeenCalled()
  })

  describe('lockout', () => {
    it('reports a lockout distinctly from bad credentials', async () => {
      loginMock.mockRejectedValue({
        isAxiosError: true,
        response: { status: 429, headers: { 'retry-after': '900' }, data: {} },
      })

      const store = useAuthStore()
      await expect(store.login(CREDENTIALS)).rejects.toBeDefined()

      expect(store.error).toBe('locked_out')
      expect(store.lockoutSeconds).toBe(900)
    })

    it('copes with a missing Retry-After header', async () => {
      loginMock.mockRejectedValue({
        isAxiosError: true,
        response: { status: 429, headers: {}, data: {} },
      })

      const store = useAuthStore()
      await expect(store.login(CREDENTIALS)).rejects.toBeDefined()

      expect(store.error).toBe('locked_out')
      expect(store.lockoutSeconds).toBeNull()
    })

    it('still reports a 401 as bad credentials', async () => {
      loginMock.mockRejectedValue({ isAxiosError: true, response: { status: 401, data: {} } })

      const store = useAuthStore()
      await expect(store.login(CREDENTIALS)).rejects.toBeDefined()

      expect(store.error).toBe('invalid_credentials')
    })
  })

  // Credentials were valid: the backend only checks maintenance after that
  // (maintenance_policy.py), and this user just isn't exempt.
  describe('maintenance mode', () => {
    it('maps a 503 MaintenanceModeError to "maintenance"', async () => {
      loginMock.mockRejectedValue({
        isAxiosError: true,
        response: { status: 503, data: { code: 'MaintenanceModeError' } },
      })

      const store = useAuthStore()
      await expect(store.login(CREDENTIALS)).rejects.toBeDefined()

      expect(store.error).toBe('maintenance')
    })

    it('leaves a plain 503 without the code as "unknown"', async () => {
      loginMock.mockRejectedValue({
        isAxiosError: true,
        response: { status: 503, data: {} },
      })

      const store = useAuthStore()
      await expect(store.login(CREDENTIALS)).rejects.toBeDefined()

      expect(store.error).toBe('unknown')
    })
  })

  describe('forced 2FA enrolment', () => {
    const SETUP = {
      totp_setup_required: true,
      setup_token: 'setup-tok',
      username: 'tester',
    }

    it('never falls through to signing the user in', async () => {
      // Unhandled, this third response variant would reach
      // useCurrentUserStore().refresh() with no session cookie ever set,
      // which would 401 against /users/me instead of leaving the user on
      // the enrolment step.
      loginMock.mockResolvedValue(SETUP)

      await useAuthStore().login(CREDENTIALS)

      expect(refreshMock).not.toHaveBeenCalled()
    })

    it('enters the enrolment step and keeps the username for display', async () => {
      loginMock.mockResolvedValue(SETUP)

      const store = useAuthStore()
      await store.login(CREDENTIALS)

      expect(store.totpSetupRequired).toBe(true)
      expect(store.setupUsername).toBe('tester')
    })

    it('fetches the secret so a QR code can be rendered', async () => {
      loginMock.mockResolvedValue(SETUP)

      const store = useAuthStore()
      await store.login(CREDENTIALS)

      expect(enrollMock).toHaveBeenCalledWith('setup-tok')
      expect(store.setupSecret).toBe('S3CR3T')
      expect(store.setupProvisioningUri).toBe('otpauth://x')
    })

    it('signs the user in once confirm sets the real session cookie', async () => {
      loginMock.mockResolvedValue(SETUP)
      confirmMock.mockResolvedValue({ access_token: 'real-tok', token_type: 'bearer' })

      const store = useAuthStore()
      await store.login(CREDENTIALS)
      await store.submitForcedEnrolment('123456')

      expect(confirmMock).toHaveBeenCalledWith('setup-tok', '123456')
      expect(refreshMock).toHaveBeenCalledOnce()
      expect(store.totpSetupRequired).toBe(false)
    })

    it('stays on the enrolment step when the code is rejected', async () => {
      loginMock.mockResolvedValue(SETUP)
      confirmMock.mockRejectedValue({ isAxiosError: true, response: { status: 401, data: {} } })

      const store = useAuthStore()
      await store.login(CREDENTIALS)
      await expect(store.submitForcedEnrolment('000000')).rejects.toBeDefined()

      expect(store.totpSetupRequired).toBe(true)
      expect(refreshMock).not.toHaveBeenCalled()
    })
  })
})

describe('authStore.submitTotp', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // The `code` field is the backend's stable discriminator between a dead
  // challenge (send the user back to credentials) and a wrong code (let
  // them retry in place). See exception_handlers.py /
  // totp_login.py:TOTPChallengeInvalidError / InvalidTOTPCodeError.
  async function submitAndReject(code: string) {
    loginMock.mockResolvedValue({ totp_required: true, partial_token: 'partial' })
    verifyTotpMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 401, data: { code } },
    })

    const store = useAuthStore()
    await store.login(CREDENTIALS)
    await expect(store.submitTotp('000000')).rejects.toBeDefined()
    return store
  }

  it('maps TOTPChallengeInvalidError to "expired"', async () => {
    const store = await submitAndReject('TOTPChallengeInvalidError')
    expect(store.totpError).toBe('expired')
  })

  it('maps InvalidTOTPCodeError to "invalid_code"', async () => {
    const store = await submitAndReject('InvalidTOTPCodeError')
    expect(store.totpError).toBe('invalid_code')
  })

  it('maps an unrecognized code to "unknown" rather than assuming invalid_code', async () => {
    const store = await submitAndReject('SomeFutureError')
    expect(store.totpError).toBe('unknown')
  })

  it('signs the user in via the session cookie on success', async () => {
    loginMock.mockResolvedValue({ totp_required: true, partial_token: 'partial' })
    verifyTotpMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })

    const store = useAuthStore()
    await store.login(CREDENTIALS)
    await store.submitTotp('123456')

    expect(refreshMock).toHaveBeenCalledOnce()
    expect(store.totpRequired).toBe(false)
  })
})

describe('authStore trusted device', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('picks up the advertised trust window from the challenge', async () => {
    loginMock.mockResolvedValue({
      totp_required: true,
      partial_token: 'partial',
      trusted_device_days: 30,
    })

    const store = useAuthStore()
    await store.login(CREDENTIALS)

    expect(store.trustedDeviceDays).toBe(30)
  })

  it('defaults to 0 (checkbox hidden) when the backend sends nothing', async () => {
    loginMock.mockResolvedValue({ totp_required: true, partial_token: 'partial' })

    const store = useAuthStore()
    await store.login(CREDENTIALS)

    expect(store.trustedDeviceDays).toBe(0)
  })

  it('passes the ticked checkbox through to verifyTotp', async () => {
    loginMock.mockResolvedValue({
      totp_required: true,
      partial_token: 'partial',
      trusted_device_days: 30,
    })
    verifyTotpMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })

    const store = useAuthStore()
    await store.login(CREDENTIALS)
    store.trustDevice = true
    await store.submitTotp('123456')

    expect(verifyTotpMock).toHaveBeenCalledWith('partial', '123456', true)
    // Consumed: the next challenge starts unticked.
    expect(store.trustDevice).toBe(false)
  })

  it('sends trust_device=false when the box is left unticked', async () => {
    loginMock.mockResolvedValue({
      totp_required: true,
      partial_token: 'partial',
      trusted_device_days: 30,
    })
    verifyTotpMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })

    const store = useAuthStore()
    await store.login(CREDENTIALS)
    await store.submitTotp('123456')

    expect(verifyTotpMock).toHaveBeenCalledWith('partial', '123456', false)
  })

  it('clears the trust state when the user backs out of the challenge', async () => {
    loginMock.mockResolvedValue({
      totp_required: true,
      partial_token: 'partial',
      trusted_device_days: 30,
    })

    const store = useAuthStore()
    await store.login(CREDENTIALS)
    store.trustDevice = true
    store.cancelTotp()

    expect(store.trustedDeviceDays).toBe(0)
    expect(store.trustDevice).toBe(false)
  })
})
