import { webApi } from '@/core/api/webRequest'
import type { NotificationResponse } from '../types/notificationTypes'

export async function getNotifications(): Promise<NotificationResponse[]> {
  const response = await webApi.get('/notifications/')
  return response.items
}
