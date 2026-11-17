import { webApi } from '@/core/api/webRequest'

export async function deleteUserSession(userId: number): Promise<void> {
  await webApi.delete('/users/{user_id}/session', { path: { user_id: userId } })
}
