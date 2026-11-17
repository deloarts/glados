import axios from 'axios'
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getUserAvatar } from '@/core/api/users/getUserAvatar'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import { login as requestLogin, verifyTotp as requestVerifyTotp } from '../api/login'
import { loginWithPasskey as requestPasskeyLogin, passkeyLoginOptions } from '../api/passkeys'
import { confirmTotpWithSetupToken, enrollTotpWithSetupToken } from '../api/totp'
import { avatarToDataUrl, rememberUser, updateRememberedUser } from '../utils/rememberedUsers'
import { getPasskey, passkeyPromptDismissed } from '../utils/webauthn'

import type { LoginRequest } from '../types/authRequest'

export type LoginErrorCode =
  | 'invalid_credentials'
  | 'inactive'
  | 'local_login_disabled'
  | 'locked_out'
  | 'maintenance'
  | 'unknown'
export type TotpErrorCode = 'invalid_code' | 'expired' | 'unknown'
export type PasskeyErrorCode =
  | 'rejected'
  | 'password_required'
  | 'inactive'
  | 'maintenance'
  | 'unknown'

/** How a passkey sign-in attempt ended; anything but 'signed_in' falls back to the password. */
export type PasskeyLoginOutcome = 'signed_in' | 'dismissed' | 'failed'

export const useAuthStore = defineStore('auth', () => {
  const loading = ref(false)
  const error = ref<LoginErrorCode | null>(null)

  /** Seconds until a lockout lapses, for the "try again in N minutes" message. */
  const lockoutSeconds = ref<number | null>(null)

  const totpRequired = ref(false)
  const partialToken = ref<string | null>(null)
  const totpError = ref<TotpErrorCode | null>(null)

  // Trusted-device lifetime in days (0 hides the checkbox) and the user's choice.
  const trustedDeviceDays = ref(0)
  const trustDevice = ref(false)

  // Forced enrolment. The setup token stays in memory, never as the session
  // token, or the router guard would treat the user as signed in.
  const totpSetupRequired = ref(false)
  const setupToken = ref<string | null>(null)
  const setupUsername = ref<string | null>(null)
  const setupSecret = ref<string | null>(null)
  const setupProvisioningUri = ref<string | null>(null)

  async function login(credentials: LoginRequest): Promise<void> {
    loading.value = true
    error.value = null
    lockoutSeconds.value = null

    try {
      const response = await requestLogin(credentials)

      // Neither restricted outcome sets the session cookie, so refresh() would 401.
      if ('totp_setup_required' in response) {
        totpSetupRequired.value = true
        setupToken.value = response.setup_token
        setupUsername.value = response.username
        await startForcedEnrolment()
        return
      }

      if ('totp_required' in response) {
        totpRequired.value = true
        partialToken.value = response.partial_token
        trustedDeviceDays.value = response.trusted_device_days ?? 0
        return
      }

      await useCurrentUserStore().refresh()
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 429) {
        // Locked out; Retry-After lets the UI say how long.
        error.value = 'locked_out'
        const retryAfter = Number(e.response.headers?.['retry-after'])
        lockoutSeconds.value = Number.isFinite(retryAfter) ? retryAfter : null
      } else if (axios.isAxiosError(e) && e.response?.status === 401) {
        error.value = 'invalid_credentials'
      } else if (axios.isAxiosError(e) && e.response?.status === 403) {
        // Inactive account or password login disabled globally. Match on
        // `code`, never on the translatable `detail` prose.
        error.value =
          e.response.data?.code === 'LocalLoginDisabledError' ? 'local_login_disabled' : 'inactive'
      } else if (
        axios.isAxiosError(e) &&
        e.response?.status === 503 &&
        e.response.data?.code === 'MaintenanceModeError'
      ) {
        // Credentials were valid, but this user is not exempt from maintenance.
        error.value = 'maintenance'
      } else {
        error.value = 'unknown'
      }

      throw e
    } finally {
      loading.value = false
    }
  }

  const passkeyError = ref<PasskeyErrorCode | null>(null)

  /**
   * Signs in with a passkey. `credentialId` is the passkey this device
   * registered for the remembered user, so the prompt goes straight to it.
   * A dismissed prompt is no error: the page offers the password instead.
   * A passkey the server no longer knows is forgotten on this device.
   */
  async function loginWithPasskey(
    username: string,
    credentialId: string | null,
  ): Promise<PasskeyLoginOutcome> {
    loading.value = true
    error.value = null
    passkeyError.value = null

    try {
      const challenge = await passkeyLoginOptions()
      const credential = await getPasskey(challenge.options, credentialId)
      await requestPasskeyLogin(challenge.challenge_token, credential)
      const currentUser = useCurrentUserStore()
      await currentUser.refresh()
      // The passkey the browser picked is the one to offer next time, also
      // when the prompt was not narrowed to a remembered one.
      if (currentUser.user?.username) {
        rememberUser({
          username: currentUser.user.username,
          fullName: currentUser.user.full_name ?? '',
          credentialId: credential.rawId as string,
        })
      }
      return 'signed_in'
    } catch (e) {
      if (passkeyPromptDismissed(e)) return 'dismissed'

      const code = axios.isAxiosError(e) ? e.response?.data?.code : null
      switch (code) {
        case 'PasskeyRejectedError':
          passkeyError.value = 'rejected'
          updateRememberedUser(username, { credentialId: null, passkeyPublicId: null })
          break
        case 'PasskeyPasswordRequiredError':
          passkeyError.value = 'password_required'
          break
        case 'InactiveUserError':
          passkeyError.value = 'inactive'
          break
        case 'MaintenanceModeError':
          passkeyError.value = 'maintenance'
          break
        default:
          passkeyError.value = 'unknown'
      }
      return 'failed'
    } finally {
      loading.value = false
    }
  }

  /**
   * Remembers the signed-in user on this device for the next visit to the
   * login page, with a small copy of the avatar. Best effort: a failure
   * only means the next login shows the plain form.
   */
  async function rememberSignedInUser(): Promise<void> {
    const user = useCurrentUserStore().user
    if (!user?.username) return

    let avatar: string | null = null
    if (user.has_avatar) {
      try {
        const blob = await getUserAvatar(user.id)
        avatar = blob ? await avatarToDataUrl(blob) : null
      } catch {
        avatar = null
      }
    }
    rememberUser({ username: user.username, fullName: user.full_name ?? '', avatar })
  }

  function clearPasskeyError(): void {
    passkeyError.value = null
  }

  async function submitTotp(code: string): Promise<void> {
    if (!partialToken.value) return

    loading.value = true
    totpError.value = null

    try {
      // The session cookie signs the user in; the body's token is unused.
      await requestVerifyTotp(partialToken.value, code, trustDevice.value)
      totpRequired.value = false
      partialToken.value = null
      trustDevice.value = false
      trustedDeviceDays.value = 0
      await useCurrentUserStore().refresh()
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        // An expired challenge means starting over, a wrong code means retry.
        switch (e.response.data?.code) {
          case 'TOTPChallengeInvalidError':
            totpError.value = 'expired'
            break
          case 'InvalidTOTPCodeError':
            totpError.value = 'invalid_code'
            break
          default:
            totpError.value = 'unknown'
        }
      } else {
        totpError.value = 'unknown'
      }

      throw e
    } finally {
      loading.value = false
    }
  }

  async function startForcedEnrolment(): Promise<void> {
    if (!setupToken.value) return

    try {
      const data = await enrollTotpWithSetupToken(setupToken.value)
      setupSecret.value = data.secret
      setupProvisioningUri.value = data.provisioning_uri
    } catch {
      totpError.value = 'unknown'
    }
  }

  /** Unlike voluntary enrolment, confirming a forced one returns a real session. */
  async function submitForcedEnrolment(code: string): Promise<void> {
    if (!setupToken.value) return

    loading.value = true
    totpError.value = null

    try {
      await confirmTotpWithSetupToken(setupToken.value, code)
      totpSetupRequired.value = false
      setupToken.value = null
      setupSecret.value = null
      setupProvisioningUri.value = null
      await useCurrentUserStore().refresh()
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        // An invalid code and an expired setup token both arrive as 401.
        totpError.value = 'invalid_code'
      } else {
        totpError.value = 'unknown'
      }

      throw e
    } finally {
      loading.value = false
    }
  }

  function cancelTotp(): void {
    totpRequired.value = false
    partialToken.value = null
    totpError.value = null
    trustedDeviceDays.value = 0
    trustDevice.value = false
    totpSetupRequired.value = false
    setupToken.value = null
    setupUsername.value = null
    setupSecret.value = null
    setupProvisioningUri.value = null
  }

  return {
    loading,
    error,
    lockoutSeconds,
    totpRequired,
    totpError,
    trustedDeviceDays,
    trustDevice,
    totpSetupRequired,
    setupUsername,
    setupSecret,
    setupProvisioningUri,
    submitForcedEnrolment,
    passkeyError,

    login,
    loginWithPasskey,
    rememberSignedInUser,
    clearPasskeyError,
    submitTotp,
    cancelTotp,
  }
})
