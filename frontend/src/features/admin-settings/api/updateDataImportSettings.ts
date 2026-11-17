import { webApi } from '@/core/api/webRequest'
import type {
  AdminDataImportSettings,
  UpdateDataImportSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateDataImportSettings(
  cmd: UpdateDataImportSettingsCommand,
): Promise<AdminDataImportSettings> {
  return webApi.put('/admin/settings/data-import', { body: cmd })
}
