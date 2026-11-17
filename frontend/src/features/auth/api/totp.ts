import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

export type TotpEnrollResponse = Schemas['TOTPEnrollResponse']

/** `access_token` is only present when a forced enrolment is confirmed. */
export type TotpConfirmResponse = Schemas['TOTPConfirmResponse']

/** Enrolment from a session confirms the current password. */
export async function enrollTotp(password: string): Promise<TotpEnrollResponse> {
  return webApi.post('/users/me/totp/enroll', { body: { password } })
}

export async function confirmTotp(totp_code: string): Promise<void> {
  await webApi.post('/users/me/totp/confirm', { body: { totp_code } })
}

export async function disableTotp(totp_code: string): Promise<void> {
  await webApi.delete('/users/me/totp/', { body: { totp_code } })
}

/**
 * Enrolment during a forced setup. The short-lived setup token is passed
 * explicitly rather than stored, so it never looks like a signed-in session.
 */
export async function enrollTotpWithSetupToken(setupToken: string): Promise<TotpEnrollResponse> {
  return webApi.post('/users/me/totp/enroll', {
    body: null,
    config: { headers: { Authorization: `Bearer ${setupToken}` } },
  })
}

/**
 * Confirming a forced enrolment returns a real session token; the backend
 * also sets it as the session cookie.
 */
export async function confirmTotpWithSetupToken(
  setupToken: string,
  totp_code: string,
): Promise<TotpConfirmResponse> {
  return webApi.post('/users/me/totp/confirm', {
    body: { totp_code },
    config: { headers: { Authorization: `Bearer ${setupToken}` } },
  })
}
