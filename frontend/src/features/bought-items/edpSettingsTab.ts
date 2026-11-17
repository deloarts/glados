import type { Plugin } from 'vue'

import { registerAdminSettingsTab } from '@/shared/admin-settings-tabs'
import { asyncTab } from '@/shared/utils/asyncTab'

/**
 * Adds the EPLAN Data Portal tab to the admin settings, next to the lookup
 * dialogs of this feature that use it. The app shell installs it once with
 * `app.use(edpSettingsTab)`, so the admin settings page never imports this
 * feature.
 */
export const edpSettingsTab: Plugin = {
  install(app) {
    registerAdminSettingsTab(app, {
      value: 'eplan-data-portal',
      icon: 'mdi-database-search-outline',
      component: asyncTab(() => import('./components/AdminSettingsTabEplanDataPortal.vue')),
      // Between SolidWorks PDM and Data Import.
      order: 145,
    })
  },
}
