import { webApi } from '@/core/api/webRequest'
import type {
  AdminProductionSettings,
  UpdateProductionSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateProductionSettings(
  cmd: UpdateProductionSettingsCommand,
): Promise<AdminProductionSettings> {
  return webApi.put('/admin/settings/production', { body: cmd })
}
