import { inject, type App, type Component, type InjectionKey, type Ref } from 'vue'

import { appRegistry } from '@/shared/utils/appRegistry'

/** Whether a registered account tab applies to the signed-in user, and its icon. */
export interface AccountTabAccess {
  /** Whether the tab shows in the tab strip. */
  visible: Readonly<Ref<boolean>>
  /**
   * Whether a route to the tab is kept. It may stay true while the tab is
   * hidden, so a deep link survives until the host capabilities are known;
   * once it turns false the page falls back to My Account.
   */
  allowed: Readonly<Ref<boolean>>
  /** The MDI icon class shown before the label. */
  icon: Readonly<Ref<string>>
}

/** One tab of the account page that a feature above Platform contributes. */
export interface AccountTab {
  /** The route segment `/account/<value>`. */
  value: string
  labelKey: string
  /** The tab panel, wrapped in `asyncTab()` so it loads only when opened. */
  component: Component
  /**
   * The position in the tab strip, ascending. The account page gives its
   * own tabs the multiples of ten, and a registered tab takes the number of
   * the place it belongs.
   */
  order: number
  /** Called during the account page's setup, so it may use composables. */
  useAccess: () => AccountTabAccess
}

/**
 * What a registered My Account section exposes, so the page's single Save
 * button saves it alongside the profile.
 */
export interface AccountSectionHandle {
  isDirty: boolean
  saving: boolean
  save(): Promise<void>
}

/**
 * A section a feature above Platform adds to My Account, below the regional
 * settings. The component exposes an `AccountSectionHandle`.
 */
export interface AccountSection {
  key: string
  component: Component
  /** The position among the registered sections, ascending. */
  order: number
  /** Called during the page's setup; a hidden section is not mounted. */
  useVisible: () => Readonly<Ref<boolean>>
}

export const accountTabsKey: InjectionKey<AccountTab[]> = Symbol('accountTabs')
export const accountSectionsKey: InjectionKey<AccountSection[]> = Symbol('accountSections')

/**
 * Adds a tab of a feature above Platform to the account page. The feature
 * calls this from the plugin `main.ts` installs, so the page renders the tab
 * without importing the feature.
 */
export function registerAccountTab(app: App, tab: AccountTab): void {
  appRegistry(app, accountTabsKey).push(tab)
}

/** Adds a section of a feature above Platform to My Account, the same way. */
export function registerAccountSection(app: App, section: AccountSection): void {
  appRegistry(app, accountSectionsKey).push(section)
}

/** The account tabs features registered, in registration order. */
export function useRegisteredAccountTabs(): readonly AccountTab[] {
  return inject(accountTabsKey, [])
}

/** The My Account sections features registered, sorted by their order. */
export function useRegisteredAccountSections(): readonly AccountSection[] {
  return [...inject(accountSectionsKey, [])].sort((a, b) => a.order - b.order)
}
