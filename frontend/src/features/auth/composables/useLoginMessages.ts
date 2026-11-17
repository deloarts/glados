import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../stores/authStore'

/**
 * The sign-in error the login card shows under the credentials. A bounce
 * reason from the api interceptor, session expired or maintenance lockout,
 * shows until the store reports an error of its own.
 */
export function useLoginErrorMessage(sessionExpired: Ref<boolean>, maintenanceLockout: Ref<boolean>) {
  const { t } = useI18n()
  const authStore = useAuthStore()

  return computed(() => {
    if (sessionExpired.value && !authStore.error) {
      return t('login.errors.sessionExpired')
    }

    if (maintenanceLockout.value && !authStore.error) {
      return t('login.errors.maintenanceLockout')
    }

    switch (authStore.error) {
      case 'invalid_credentials':
        return t('login.errors.invalidCredentials')
      case 'inactive':
        return t('login.errors.inactive')
      case 'local_login_disabled':
        return t('login.errors.localLoginDisabled')
      case 'locked_out':
        return authStore.lockoutSeconds
          ? t('login.errors.lockedOutFor', {
              count: Math.max(1, Math.ceil(authStore.lockoutSeconds / 60)),
            })
          : t('login.errors.lockedOut')
      case 'maintenance':
        return t('login.errors.maintenance')
      case 'unknown':
        return t('login.errors.unknown')
      default:
        return null
    }
  })
}

/** Why the last passkey sign-in failed, or null. */
export function usePasskeyErrorMessage() {
  const { t } = useI18n()
  const authStore = useAuthStore()

  return computed(() => {
    switch (authStore.passkeyError) {
      case 'rejected':
        return t('login.passkey.errors.rejected')
      case 'password_required':
        return t('login.passkey.errors.passwordRequired')
      case 'inactive':
        return t('login.errors.inactive')
      case 'maintenance':
        return t('login.errors.maintenance')
      case 'unknown':
        return t('login.passkey.errors.unknown')
      default:
        return null
    }
  })
}

/** Why the last two-factor code was refused, or null. */
export function useTotpErrorMessage() {
  const { t } = useI18n()
  const authStore = useAuthStore()

  return computed(() => {
    switch (authStore.totpError) {
      case 'invalid_code':
        return t('login.totp.errors.invalidCode')
      case 'expired':
        return t('login.totp.errors.expired')
      case 'unknown':
        return t('login.totp.errors.unknown')
      default:
        return null
    }
  })
}
