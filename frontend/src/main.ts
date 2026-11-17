import { createApp } from 'vue'
import { createPinia } from 'pinia'

import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { i18n } from '@/core/i18n'
import { defaultThemePreset } from '@/core/config/themePresets'
import { storeResetPlugin } from '@/core/stores/resetOnLogout'
import { installGlobalErrorHandlers } from '@/core/errors/installGlobalErrorHandlers'
import { settleConfirmationsOnce } from '@/core/confirm/settleConfirmationsOnce'
import { installUserActivityTracking } from '@/core/session/userActivity'
import { installSelectionClickGuard } from '@/core/utils/selectionClickGuard'
import { pruneLocalDrafts } from '@/shared/documents/utils/localDraft'
import { handbookHelp } from '@/features/handbook'
import { templatePrinting } from '@/features/print-labels'
// Imported from their modules rather than the barrels, which would pull the
// production and bought item screens into the entry chunk.
import { edpSettingsTab } from '@/features/bought-items/edpSettingsTab'
import { productionSettingsTab } from '@/features/production/productionSettingsTab'
import { timeTrackingSections } from '@/features/time-tracking/timeTrackingSections'
import { agentSections } from '@/features/agents/agentSections'

import App from '@/App.vue'
import router from '@/router'

import '@fontsource-variable/inter'
import '@mdi/font/css/materialdesignicons.css'
import '@/assets/styles/fonts.css'
import '@/assets/styles/main.scss'
import '@/assets/styles/aperture.scss'

function bootstrap(): void {
  const pinia = createPinia()
  pinia.use(storeResetPlugin)
  const app = createApp(App)

  app.use(pinia)
  app.use(router)
  app.use(i18n)

  app.use(OpenVue, {
    theme: {
      preset: defaultThemePreset,
      options: {
        darkModeSelector: '.p-dark',
      },
    },
    ripple: true,
    locale: {
      // No DatePicker passes `dateFormat` itself, they all inherit from here,
      // and useOpenVueLocale() (App.vue) keeps this in step with the
      // signed-in user's preference. Seeded with ISO so the login screen and
      // any component mounted outside App.vue don't fall back to OpenVue's
      // own 'mm/dd/yy' default.
      dateFormat: 'yy-mm-dd',
      // Weeks start on Monday, as they do on the shop floor's calendar and
      // in ISO 8601, whatever the browser's own locale says.
      firstDayOfWeek: 1,
    },
  })

  app.use(ToastService)
  app.use(ConfirmationService)
  app.use(settleConfirmationsOnce)
  app.directive('tooltip', Tooltip)
  // Every help button and explain drawer shows handbook docs through this.
  app.use(handbookHelp)
  // Every label and docket a screen prints goes through the print templates.
  app.use(templatePrinting)
  // The tabs and sections features above Platform add to the account page
  // and the admin settings, which never import those features.
  app.use(timeTrackingSections)
  app.use(productionSettingsTab)
  app.use(edpSettingsTab)
  app.use(agentSections)

  installGlobalErrorHandlers(app)
  installUserActivityTracking()
  installSelectionClickGuard()
  pruneLocalDrafts()

  app.mount('#app')
}

bootstrap()
