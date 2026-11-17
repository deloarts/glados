import { webApi } from '@/core/api/webRequest'

export async function markNotificationRead(notificationId: number): Promise<void> {
  await webApi.patch('/notifications/{notification_id}/read', {
    path: { notification_id: notificationId },
  })
}
