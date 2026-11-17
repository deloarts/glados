import { webApi } from '@/core/api/webRequest'
import type { AdminBrandingSettings } from '../types/adminSettingsTypes'

export async function deleteBrandingLogo(): Promise<AdminBrandingSettings> {
  return webApi.delete('/admin/settings/branding/logo')
}
