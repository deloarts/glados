import { webApi } from '@/core/api/webRequest'
import type { AdminMailSettings, UpdateMailSettingsCommand } from '../types/adminSettingsTypes'

export async function updateMailSettings(
  cmd: UpdateMailSettingsCommand,
): Promise<AdminMailSettings> {
  return webApi.put('/admin/settings/mail', { body: cmd })
}
