import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import router from '@/router'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'
import { setDisplayDateFormat } from '@/core/utils/dates'
import { useUserAvatarsStore } from '@/core/stores/userAvatarsStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { resetAllStores, clearPersistedDrafts } from '@/core/stores/resetOnLogout'

import { getCurrentUser } from '@/core/api/users/getCurrentUser'
import { getCurrentSession } from '@/core/api/users/getCurrentSession'
import { postLogout } from '@/core/api/users/postLogout'
import { Permission } from '@/core/auth/permissions'

import type { UserResponse } from '@/core/types/userResponse'

// sessionStorage, so the warning returns on every new sign-in or tab but
// not on a reload.
export const SYSTEM_USER_WARNING_SESSION_KEY = 'gladosSystemUserWarningShown'

function systemUserWarningAlreadyShown(): boolean {
  try {
    return sessionStorage.getItem(SYSTEM_USER_WARNING_SESSION_KEY) !== null
  } catch {
    return false
  }
}

function markSystemUserWarningShown(): void {
  try {
    sessionStorage.setItem(SYSTEM_USER_WARNING_SESSION_KEY, '1')
  } catch {
    // Best effort; worst case the warning reappears next reload this tab.
  }
}

function clearSystemUserWarningShown(): void {
  try {
    sessionStorage.removeItem(SYSTEM_USER_WARNING_SESSION_KEY)
  } catch {
    // Best effort; see markSystemUserWarningShown.
  }
}

export const useCurrentUserStore = defineStore('currentUser', () => {
  const loading = ref(false)
  const user = ref<UserResponse | null>(null)
  // System users only; null hides the countdown rather than showing a
  // wrong number.
  const sessionExpiresAt = ref<number | null>(null)
  // Only acknowledging or the session ending clears it, so a reload does not.
  const systemUserWarningPending = ref(false)
  // The httponly session cookie is invisible here, so the router guard
  // probes once per app load and reads this afterwards.
  const sessionChecked = ref(false)

  const isAuthenticated = computed(() => !!user.value)

  const isAdmin = computed(() => {
    if (!user.value) return false
    if (user.value.is_systemuser) return true
    return user.value.permissions.includes(Permission.READ_SETTINGS)
  })

  const isSharedAccount = computed(() => user.value?.is_shared_account ?? false)

  /**
   * The hard expiry corrected for clock skew using the server's own time.
   * Never throws, so a failed fetch cannot fail sign-in.
   */
  async function fetchSessionExpiry() {
    try {
      const { expires_at, server_time } = await getCurrentSession()
      if (expires_at === null) {
        sessionExpiresAt.value = null
        return
      }
      const skewMs = Date.parse(server_time) - Date.now()
      sessionExpiresAt.value = Date.parse(expires_at) - skewMs
    } catch {
      sessionExpiresAt.value = null
    }
  }

  async function refresh() {
    loading.value = true

    try {
      const response = await getCurrentUser()
      user.value = response

      if (response.is_systemuser) {
        await fetchSessionExpiry()
        if (!systemUserWarningAlreadyShown()) {
          systemUserWarningPending.value = true
        }
      } else {
        sessionExpiresAt.value = null
      }

      i18n.global.locale.value = response.language as 'enGB' | 'deAT'
      setDisplayDateFormat(response.date_format)
      const { applyUserTheme, applyVisualAids } = useLayoutStore()
      applyUserTheme(
        response.theme_preset,
        response.theme_primary,
        response.theme_surface,
        response.theme_dark_mode,
      )
      applyVisualAids(
        response.button_flat_style,
        response.table_gridlines,
        response.table_striped_rows,
      )
    } finally {
      loading.value = false
      sessionChecked.value = true
    }
  }

  /** Records the warning as acknowledged for this tab and hides it. */
  function acknowledgeSystemUserWarning() {
    systemUserWarningPending.value = false
    markSystemUserWarningShown()
  }

  /**
   * The login page language from public branding. Read before
   * resetAllStores(), which wipes that store; falls back to 'enGB'.
   */
  function tenantDefaultLocale(): AppLocale {
    return (usePublicBrandingStore().branding?.default_language ?? 'enGB') as AppLocale
  }

  /**
   * Shared teardown for every way a session ends: clears the cookie (best
   * effort), every store and the user's preferences, and switches i18n to
   * the tenant default for whoever signs in next.
   */
  function teardownSession(): void {
    void postLogout().catch(() => {
      // Best effort; the teardown proceeds regardless.
    })
    const loginLocale = tenantDefaultLocale()
    resetAllStores()
    clearPersistedDrafts()

    user.value = null
    sessionExpiresAt.value = null
    systemUserWarningPending.value = false
    clearSystemUserWarningShown()
    i18n.global.locale.value = loginLocale
    setDisplayDateFormat(null)
    // Nothing else revokes the cached avatar blob URLs.
    useUserAvatarsStore().clear()
  }

  function logout() {
    teardownSession()

    void router.push({
      name: 'Login',
    })
  }

  /**
   * The session ending underneath the user. It keeps the current route for
   * after sign-in and tells the login screen why. Several failing requests
   * may call it at once, hence the no-op once the session is gone.
   */
  function sessionExpired() {
    if (!user.value) return

    teardownSession()

    const current = router.currentRoute.value
    if (current.name === 'Login') return

    void router.push({
      name: 'Login',
      query: {
        reason: 'expired',
        ...(current.fullPath !== '/' ? { redirect: current.fullPath } : {}),
      },
    })
  }

  /**
   * Like sessionExpired(), but because maintenance mode started, so the
   * login screen shows the maintenance notice.
   */
  function maintenanceLockout() {
    if (!user.value) return

    teardownSession()

    const current = router.currentRoute.value
    if (current.name === 'Login') return

    void router.push({
      name: 'Login',
      query: {
        reason: 'maintenance',
        ...(current.fullPath !== '/' ? { redirect: current.fullPath } : {}),
      },
    })
  }

  return {
    loading,
    user,
    sessionExpiresAt,
    systemUserWarningPending,
    sessionChecked,

    isAuthenticated,
    isAdmin,
    isSharedAccount,

    refresh,
    logout,
    sessionExpired,
    maintenanceLockout,
    acknowledgeSystemUserWarning,
  }
})
