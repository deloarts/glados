import { webApi } from '@/core/api/webRequest'
import type {
  SaveTimeTrackingCredentialsRequest,
  TimeTrackingAccountResponse,
  TimeTrackingMonthResponse,
  TimeTrackingYearResponse,
} from '../types/timeTrackingTypes'

/**
 * The signed-in user's own time tracking routes. Only the month and year
 * reads, the save and the access check reach the time tracking system;
 * reading the account is Glados data only and costs that system nothing.
 */

export async function getMyTimeTrackingAccount(): Promise<TimeTrackingAccountResponse> {
  return webApi.get('/time-tracking/me/account')
}

/**
 * Verifies the credentials with a sign-in and stores them only when it
 * succeeds. An omitted or null password keeps the stored one.
 */
export async function saveMyTimeTrackingAccount(
  body: SaveTimeTrackingCredentialsRequest,
): Promise<TimeTrackingAccountResponse> {
  return webApi.put('/time-tracking/me/account', { body })
}

/** Removes the stored credentials together with the stored consent. */
export async function deleteMyTimeTrackingAccount(): Promise<void> {
  await webApi.delete('/time-tracking/me/account')
}

/**
 * Signs in with the stored credentials and reports which journals the
 * account may read. Nothing is stored.
 */
export async function checkMyTimeTrackingAccess(): Promise<TimeTrackingAccountResponse> {
  return webApi.post('/time-tracking/me/account/check')
}

/** One month, `month` as "YYYY-MM", fetched live. */
export async function getMyTimeTrackingMonth(month: string): Promise<TimeTrackingMonthResponse> {
  return webApi.get('/time-tracking/me/month', { query: { month } })
}

/** One year's month-by-month summary, fetched live. */
export async function getMyTimeTrackingYear(year: number): Promise<TimeTrackingYearResponse> {
  return webApi.get('/time-tracking/me/year', { query: { year } })
}
