import type { Plugin } from 'vue'

import { helpProviderKey, type HelpProvider } from '@/shared/help'

import HandbookDrawer from './components/HandbookDrawer.vue'
import { hasHandbookDoc } from './utils/handbookContent'

/**
 * Installs the handbook as the app's help provider, so every HelpButton and
 * HelpDrawer shows handbook docs. The app shell installs it once with
 * `app.use(handbookHelp)`, which keeps the handbook a leaf no feature imports.
 */
export const handbookHelp: Plugin = {
  install(app) {
    const provider: HelpProvider = { has: hasHandbookDoc, drawer: HandbookDrawer }
    app.provide(helpProviderKey, provider)
  },
}
