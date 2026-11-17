import { webApi } from '@/core/api/webRequest'
import type {
  AdminFeatureSettings,
  UpdateFeatureSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateFeatureSettings(
  cmd: UpdateFeatureSettingsCommand,
): Promise<AdminFeatureSettings> {
  return webApi.put('/admin/settings/features', { body: cmd })
}
