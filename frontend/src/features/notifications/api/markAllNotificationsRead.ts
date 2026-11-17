import { webApi } from '@/core/api/webRequest'

export async function markAllNotificationsRead(): Promise<void> {
  await webApi.patch('/notifications/read-all')
}
