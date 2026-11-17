import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

export type UserPasskeySummary = Schemas['PasskeyResult']

/** Another user's passkeys. Requires write:settings and is refused for yourself. */
export async function fetchUserPasskeys(userId: number): Promise<UserPasskeySummary[]> {
  return webApi.get('/users/{user_id}/passkeys', { path: { user_id: userId } })
}

/**
 * Removes every passkey of another user, for a lost or stolen device.
 * Requires write:settings and is refused for yourself; your own passkeys
 * are removed under Account, Passkeys.
 */
export async function resetUserPasskeys(userId: number): Promise<number> {
  const response = await webApi.delete('/users/{user_id}/passkeys', { path: { user_id: userId } })
  return response.revoked
}
