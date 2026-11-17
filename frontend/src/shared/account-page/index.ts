// Public surface of the account page registry. A feature above Platform
// that adds a tab to the account page or a section to My Account registers
// it here from its plugin, and the page renders what was registered, so
// Platform never imports the feature.
export {
  accountSectionsKey,
  accountTabsKey,
  registerAccountSection,
  registerAccountTab,
  useRegisteredAccountSections,
  useRegisteredAccountTabs,
} from './accountPage'
export type { AccountSection, AccountSectionHandle, AccountTab, AccountTabAccess } from './accountPage'
