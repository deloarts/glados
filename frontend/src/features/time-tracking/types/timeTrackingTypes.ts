/**
 * Time tracking types, aliased from the generated OpenAPI schema. The
 * names are provider-neutral like the API itself.
 */
import type { Schemas } from '@/core/api/generated'

/**
 * The user's stored credentials and whether they can be used, plus the
 * verification result after a save or an access check.
 */
export type TimeTrackingAccountResponse = Schemas['TimeTrackingAccountResponse']

export type SaveTimeTrackingCredentialsRequest = Schemas['SaveTimeTrackingCredentialsRequest']

export type TimeTrackingReadRights = Schemas['TimeTrackingReadRightsResponse']

export type TimeTrackingMonthResponse = Schemas['TimeTrackingMonthResponse']

export type TimeTrackingYearResponse = Schemas['TimeTrackingYearResponse']

export type TimeTrackingDay = Schemas['TimeTrackingDayResponse']

export type TimeTrackingBooking = Schemas['TimeTrackingBookingResponse']

export type TimeTrackingAccountValue = Schemas['TimeTrackingAccountValueResponse']

/** How an account's values are written, see accountValueFormat.ts. */
export type TimeTrackingAccountFormat = Schemas['TimeTrackingAccountFormat']

export type TimeTrackingTotals = Schemas['TimeTrackingTotalsResponse']

export type TimeTrackingToday = Schemas['TimeTrackingTodayResponse']

export type TimeTrackingYearMonth = Schemas['TimeTrackingYearMonthResponse']

export type TimeTrackingDayStatus = Schemas['TimeTrackingDayStatus']

// Listed for the i18n parity check, which reads the dynamic status keys from it.
export const TIME_TRACKING_DAY_STATUSES = [
  'normal',
  'shift_free',
  'holiday',
  'absence',
  'open',
] as const satisfies readonly TimeTrackingDayStatus[]

/** Why stored credentials cannot be used; `missing` means none are stored. */
export type TimeTrackingInvalidReason = Schemas['CredentialsInvalidReason']

export const TIME_TRACKING_INVALID_REASONS = [
  'missing',
  'undecryptable',
  'binding_changed',
  'auth_failed',
  'consent_outdated',
] as const satisfies readonly TimeTrackingInvalidReason[]
