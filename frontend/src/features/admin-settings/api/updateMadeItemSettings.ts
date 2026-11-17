import { webApi } from '@/core/api/webRequest'
import type {
  AdminMadeItemSettings,
  UpdateMadeItemSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateMadeItemSettings(
  cmd: UpdateMadeItemSettingsCommand,
): Promise<AdminMadeItemSettings> {
  return webApi.put('/admin/settings/made-items', { body: cmd })
}
