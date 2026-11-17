import { webApi } from '@/core/api/webRequest'
import type { AdminBannerSettings, UpdateBannerSettingsCommand } from '../types/adminSettingsTypes'

export async function updateBannerSettings(
  cmd: UpdateBannerSettingsCommand,
): Promise<AdminBannerSettings> {
  return webApi.put('/admin/settings/banner', { body: cmd })
}
