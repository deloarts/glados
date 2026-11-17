import { webApi } from '@/core/api/webRequest'
import type {
  AdminNotificationSettings,
  UpdateNotificationSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateNotificationSettings(
  cmd: UpdateNotificationSettingsCommand,
): Promise<AdminNotificationSettings> {
  return webApi.put('/admin/settings/notifications', { body: cmd })
}
