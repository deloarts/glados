import { webApi } from '@/core/api/webRequest'
import type {
  AdminTimeTrackingSettings,
  ConfirmTimeTrackingKeyCommand,
  PurgeTimeTrackingCredentialsResult,
  TimeTrackingServiceTestResult,
  UpdateTimeTrackingSettingsCommand,
  VerifyTimeTrackingServiceCommand,
} from '../types/adminSettingsTypes'

export async function getTimeTrackingSettings(): Promise<AdminTimeTrackingSettings> {
  return webApi.get('/admin/settings/time-tracking')
}

export async function updateTimeTrackingSettings(
  cmd: UpdateTimeTrackingSettingsCommand,
): Promise<AdminTimeTrackingSettings> {
  return webApi.put('/admin/settings/time-tracking', { body: cmd })
}

/**
 * Tests the given, possibly unsaved, time tracking service: its version,
 * contract and credential key, and the system behind it. Stores nothing.
 */
export async function testTimeTrackingService(
  cmd: VerifyTimeTrackingServiceCommand,
): Promise<TimeTrackingServiceTestResult> {
  return webApi.post('/admin/settings/time-tracking/test', { body: cmd })
}

/** Confirms the credential key the saved service serves, by the id the test showed. */
export async function confirmTimeTrackingKey(
  cmd: ConfirmTimeTrackingKeyCommand,
): Promise<AdminTimeTrackingSettings> {
  return webApi.post('/admin/settings/time-tracking/confirm-key', { body: cmd })
}

/** Deletes every user's stored time tracking credentials. Audited. */
export async function purgeTimeTrackingCredentials(): Promise<PurgeTimeTrackingCredentialsResult> {
  return webApi.delete('/admin/settings/time-tracking/credentials')
}
