import { computed, type Plugin } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'
import { registerAccountSection, registerAccountTab } from '@/shared/account-page'
import { registerAdminSettingsTab } from '@/shared/admin-settings-tabs'
import { useClockIcon } from '@/shared/composables/useClockIcon'
import { asyncTab } from '@/shared/utils/asyncTab'

import AccountTimeTrackingSection from './components/AccountTimeTrackingSection.vue'
import { useTimeTrackingAvailability } from './composables/useTimeTrackingAvailability'

/**
 * Adds the time tracking parts of the Platform pages: the Time Tracking tab
 * of the account page, the credentials section of My Account, and the time
 * tracking tab of the admin settings. The app shell installs it once with
 * `app.use(timeTrackingSections)`, so the account and admin settings pages
 * never import this feature.
 */
export const timeTrackingSections: Plugin = {
  install(app) {
    registerAccountTab(app, {
      value: 'time-tracking',
      labelKey: 'timeTracking.tab',
      component: asyncTab(() => import('./views/AccountTimeTrackingView.vue')),
      // Between My Account and Notifications.
      order: 15,
      useAccess() {
        const hostStore = useHostStore()
        const { available } = useTimeTrackingAvailability()
        return {
          // Only for personal accounts on an instance with time tracking enabled.
          visible: available,
          // Until the capabilities arrive a deep link to the tab is kept
          // rather than bounced to My Account, and resolved once they are known.
          allowed: computed(() => !hostStore.loaded || available.value),
          // The sidebar shortcut uses the same composable, so both clocks agree.
          icon: useClockIcon(),
        }
      },
    })

    registerAccountSection(app, {
      key: 'time-tracking',
      component: AccountTimeTrackingSection,
      order: 10,
      useVisible: () => useTimeTrackingAvailability().available,
    })

    registerAdminSettingsTab(app, {
      value: 'time-tracking',
      icon: 'mdi-clock-outline',
      component: asyncTab(() => import('./components/AdminSettingsTabTimeTracking.vue')),
      // Between Stock Service and AI Models.
      order: 165,
    })
  },
}
