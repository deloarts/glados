// Public surface of the admin settings tab registry. A feature above
// Platform whose settings live on the admin settings page registers its tab
// here from its plugin, and the page renders the registered tabs beside its
// own, so Platform never imports the feature.
export {
  adminSettingsTabsKey,
  registerAdminSettingsTab,
  useRegisteredAdminSettingsTabs,
} from './adminSettingsTabs'
export type { AdminSettingsTab } from './adminSettingsTabs'
