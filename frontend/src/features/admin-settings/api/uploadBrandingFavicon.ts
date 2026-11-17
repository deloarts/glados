import { postFile } from '@/core/api/postFile'
import type { AdminBrandingSettings } from '../types/adminSettingsTypes'

export async function uploadBrandingFavicon(file: File): Promise<AdminBrandingSettings> {
  return postFile('/admin/settings/branding/favicon', file)
}
