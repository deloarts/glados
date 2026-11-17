import { postFile } from '@/core/api/postFile'
import type { AdminGeneralSettings } from '../types/adminSettingsTypes'

export async function uploadCompanyLogo(file: File): Promise<AdminGeneralSettings> {
  return postFile('/admin/settings/general/company-logo', file)
}
