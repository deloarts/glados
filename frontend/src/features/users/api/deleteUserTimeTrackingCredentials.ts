import { webApi } from '@/core/api/webRequest'

/**
 * Administrative removal of one user's stored time tracking credentials,
 * the step before turning that user into a shared account, which the
 * backend refuses while credentials are stored. Requires write:settings
 * unless aimed at yourself; a no-op when nothing is stored.
 */
export async function deleteUserTimeTrackingCredentials(userId: number): Promise<void> {
  await webApi.delete('/users/{user_id}/time-tracking-credentials', { path: { user_id: userId } })
}
