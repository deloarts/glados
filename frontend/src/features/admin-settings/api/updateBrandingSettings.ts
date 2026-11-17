import { webApi } from '@/core/api/webRequest'
import type {
  AdminBrandingSettings,
  UpdateBrandingSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateBrandingSettings(
  cmd: UpdateBrandingSettingsCommand,
): Promise<AdminBrandingSettings> {
  return webApi.put('/admin/settings/branding', { body: cmd })
}
