import { webApi } from '@/core/api/webRequest'
import type {
  AdminRetentionSettings,
  UpdateRetentionSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateRetentionSettings(
  cmd: UpdateRetentionSettingsCommand,
): Promise<AdminRetentionSettings> {
  return webApi.put('/admin/settings/retention', { body: cmd })
}
