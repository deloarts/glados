import { webApi } from '@/core/api/webRequest'
import type {
  AdminGeneralSettings,
  UpdateGeneralSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateGeneralSettings(
  cmd: UpdateGeneralSettingsCommand,
): Promise<AdminGeneralSettings> {
  return webApi.put('/admin/settings/general', { body: cmd })
}
