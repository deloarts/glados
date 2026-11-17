import { computed } from 'vue'

import { i18n } from '@/core/i18n'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

/**
 * Whether the time tracking surfaces apply to the signed-in user: time
 * tracking is available on this instance and the user is a personal
 * account. Shared accounts and the system user cannot hold credentials, so
 * they never see the sidebar shortcut, the account tab or the My Account
 * section. Service accounts never sign in to the web app.
 *
 * `providerName` is the name of the time tracking system as the time
 * tracking service reports it, a product name that is not translated, or
 * the neutral wording while none is known.
 */
export function useTimeTrackingAvailability() {
  const hostStore = useHostStore()
  const userStore = useCurrentUserStore()

  const available = computed(() => {
    const user = userStore.user
    return (
      hostStore.timeTrackingEnabled && !!user && !user.is_shared_account && !user.is_systemuser
    )
  })

  const providerName = computed(
    () => hostStore.timeTrackingProviderLabel || i18n.global.t('timeTracking.providerFallback'),
  )

  return { available, providerName }
}
