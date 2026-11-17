import { webApi } from '@/core/api/webRequest'

/**
 * Administrative 2FA reset, for a user who lost their authenticator.
 *
 * Not the same as removing your own 2FA (`disableTotp`), which confirms
 * with the current code, the code being exactly what a user with a lost
 * device cannot produce. Requires write:settings and is rejected by the
 * backend if aimed at yourself or at the system user.
 */
export async function resetUserTotp(userId: number): Promise<void> {
  await webApi.delete('/users/{user_id}/totp', { path: { user_id: userId } })
}
