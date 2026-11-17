// Public barrel of the time tracking feature. Other code imports through
// here (enforced by eslint). The Time Tracking view itself is lazy-loaded
// by the account tab that `timeTrackingSections` registers and deliberately
// not exported.

export { useTimeTrackingAccountStore } from './stores/timeTrackingAccountStore'
export { useTimeTrackingAvailability } from './composables/useTimeTrackingAvailability'
export {
  checkMyTimeTrackingAccess,
  deleteMyTimeTrackingAccount,
  saveMyTimeTrackingAccount,
} from './api/timeTrackingApi'
export {
  TIME_TRACKING_ERROR_KEYS,
  isCredentialStateError,
  timeTrackingErrorMessage,
} from './utils/timeTrackingErrors'

export type {
  SaveTimeTrackingCredentialsRequest,
  TimeTrackingAccountResponse,
  TimeTrackingInvalidReason,
  TimeTrackingReadRights,
} from './types/timeTrackingTypes'

export { default as TimeTrackingConsentDialog } from './components/TimeTrackingConsentDialog.vue'
