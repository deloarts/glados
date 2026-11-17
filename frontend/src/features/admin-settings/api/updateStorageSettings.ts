import { webApi } from '@/core/api/webRequest'
import type {
  AdminStorageSettings,
  UpdateStorageSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateStorageSettings(
  cmd: UpdateStorageSettingsCommand,
): Promise<AdminStorageSettings> {
  return webApi.put('/admin/settings/storage', { body: cmd })
}
