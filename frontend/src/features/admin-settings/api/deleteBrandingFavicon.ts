import { webApi } from '@/core/api/webRequest'
import type { AdminBrandingSettings } from '../types/adminSettingsTypes'

export async function deleteBrandingFavicon(): Promise<AdminBrandingSettings> {
  return webApi.delete('/admin/settings/branding/favicon')
}
