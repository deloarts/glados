import type { Plugin } from 'vue'

import { registerAdminSettingsTab } from '@/shared/admin-settings-tabs'
import { asyncTab } from '@/shared/utils/asyncTab'

/**
 * Adds the production tab to the admin settings: scheduling, the QA default
 * with its inspection method, material approval and delivery tolerances.
 * The app shell installs it once with `app.use(productionSettingsTab)`, so
 * the admin settings page never imports this feature.
 */
export const productionSettingsTab: Plugin = {
  install(app) {
    registerAdminSettingsTab(app, {
      value: 'production',
      icon: 'mdi-robot-industrial-outline',
      component: asyncTab(() => import('./components/AdminSettingsTabProduction.vue')),
      // Between Numbering and Branding.
      order: 115,
    })
  },
}
