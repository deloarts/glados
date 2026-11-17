import { postFile } from '@/core/api/postFile'
import type { AdminBrandingSettings } from '../types/adminSettingsTypes'

export async function uploadBrandingLogo(file: File): Promise<AdminBrandingSettings> {
  return postFile('/admin/settings/branding/logo', file)
}
