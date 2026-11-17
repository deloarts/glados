import { inject, type App, type Component, type InjectionKey } from 'vue'

import { appRegistry } from '@/shared/utils/appRegistry'

/** One tab of the admin settings page. */
export interface AdminSettingsTab {
  /** The route segment `/settings/<value>`; the label is `adminSettings.tabs.<value>`. */
  value: string
  /** The MDI icon class shown before the label. */
  icon: string
  /** The tab panel, wrapped in `asyncTab()` so it loads only when opened. */
  component: Component
  /**
   * The position in the tab strip, ascending. The admin settings page gives
   * its own tabs the multiples of ten, and a registered tab takes the number
   * of the place it belongs.
   */
  order: number
}

export const adminSettingsTabsKey: InjectionKey<AdminSettingsTab[]> = Symbol('adminSettingsTabs')

/**
 * Adds a tab of a feature above Platform to the admin settings page. The
 * feature calls this from the plugin `main.ts` installs, so the page renders
 * the tab without importing the feature.
 */
export function registerAdminSettingsTab(app: App, tab: AdminSettingsTab): void {
  appRegistry(app, adminSettingsTabsKey).push(tab)
}

/** The tabs features registered, in registration order. */
export function useRegisteredAdminSettingsTabs(): readonly AdminSettingsTab[] {
  return inject(adminSettingsTabsKey, [])
}
