import authApi from '@/core/api/auth'
import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'
import type { TokenResponse } from '../types/authResponse'

export type PasskeyChallenge = Schemas['PasskeyChallenge']

export type PasskeySummary = Schemas['PasskeyResult']

/** Options for the login prompt; public, needs no session. */
export async function passkeyLoginOptions(): Promise<PasskeyChallenge> {
  const response = await authApi.post<PasskeyChallenge>('/login/passkey/options')
  return response.data
}

/** Exchanges the signed assertion for a session; the backend also sets the session cookie. */
export async function loginWithPasskey(
  challenge_token: string,
  credential: Record<string, unknown>,
): Promise<TokenResponse> {
  const response = await authApi.post<TokenResponse>('/login/passkey', {
    challenge_token,
    credential,
  })
  return response.data
}

export async function fetchMyPasskeys(): Promise<PasskeySummary[]> {
  return webApi.get('/users/me/passkeys/')
}

/** Confirms the password and returns the options for creating a passkey. */
export async function passkeyRegistrationOptions(password: string): Promise<PasskeyChallenge> {
  return webApi.post('/users/me/passkeys/registration-options', { body: { password } })
}

export async function registerPasskey(
  challenge_token: string,
  credential: Record<string, unknown>,
  name: string,
): Promise<PasskeySummary> {
  return webApi.post('/users/me/passkeys/', { body: { challenge_token, credential, name } })
}

export async function deleteMyPasskey(publicId: string): Promise<void> {
  await webApi.delete('/users/me/passkeys/{public_id}', { path: { public_id: publicId } })
}

/** Removes every passkey of the signed-in user; returns how many were removed. */
export async function deleteAllMyPasskeys(): Promise<number> {
  const response = await webApi.delete('/users/me/passkeys/')
  return response.revoked
}

export async function renameMyPasskey(publicId: string, name: string): Promise<PasskeySummary> {
  return webApi.patch('/users/me/passkeys/{public_id}', {
    path: { public_id: publicId },
    body: { name },
  })
}
