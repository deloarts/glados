import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

export type SessionSummary = Schemas['SessionResult']

export type TrustedDeviceSummary = Schemas['TrustedDeviceResult']

export async function fetchSessions(): Promise<SessionSummary[]> {
  return webApi.get('/users/me/sessions/')
}

export async function revokeSession(publicId: string): Promise<void> {
  await webApi.delete('/users/me/sessions/{public_id}', { path: { public_id: publicId } })
}

/** "Sign out everywhere else", returns how many sessions were ended. */
export async function revokeOtherSessions(): Promise<number> {
  const response = await webApi.delete('/users/me/sessions/')
  return response.revoked
}

export async function fetchTrustedDevices(): Promise<TrustedDeviceSummary[]> {
  return webApi.get('/users/me/trusted-devices/')
}

export async function revokeTrustedDevice(publicId: string): Promise<void> {
  await webApi.delete('/users/me/trusted-devices/{public_id}', { path: { public_id: publicId } })
}

export async function revokeAllTrustedDevices(): Promise<number> {
  const response = await webApi.delete('/users/me/trusted-devices/')
  return response.revoked
}
