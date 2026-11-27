// Public barrel for the admin-settings feature.
// Other features must import through here rather than reaching into
// admin-settings' internals directly (enforced by the no-restricted-imports
// rule in eslint.config.ts). The settings tabs that features above Platform
// register (see `@/shared/admin-settings-tabs`) build on the store, the save
// helper and the tab shell exported here.

export { useAdminSettingsStore } from './stores/adminSettingsStore'
export { useSettingsSave } from './composables/useSettingsSave'
export { default as AdminSettingsTabShell } from './components/AdminSettingsTabShell.vue'

export type {
  AdminEdpSettings,
  AdminOrderSettings,
  AdminPlanningSettings,
  AdminProductionSettings,
  AdminTimeTrackingSettings,
  AllAdminSettings,
  ConfirmTimeTrackingKeyCommand,
  PurgeTimeTrackingCredentialsResult,
  TimeTrackingCredentialHolder,
  TimeTrackingServiceTestResult,
  UpdateEdpSettingsCommand,
  UpdateTimeTrackingSettingsCommand,
  VerifyTimeTrackingServiceCommand,
} from './types/adminSettingsTypes'
