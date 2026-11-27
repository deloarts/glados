import type { Plugin } from 'vue'

import { registerAdminSettingsTab } from '@/shared/admin-settings-tabs'
import { asyncTab } from '@/shared/utils/asyncTab'

/**
 * Adds the planning tab to the admin settings: the committed horizon, the
 * retention of recorded plans and the start of the booking quality view.
 * The app shell installs it once with `app.use(planningSettingsTab)`, so the
 * admin settings page never imports this feature.
 */
export const planningSettingsTab: Plugin = {
  install(app) {
    registerAdminSettingsTab(app, {
      value: 'planning',
      icon: 'mdi-calendar-check-outline',
      component: asyncTab(() => import('./components/AdminSettingsTabPlanning.vue')),
      // Right after Production, before Branding.
      order: 116,
    })
  },
}
