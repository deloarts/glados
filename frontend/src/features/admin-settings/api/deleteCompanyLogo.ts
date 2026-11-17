import { webApi } from '@/core/api/webRequest'
import type { AdminGeneralSettings } from '../types/adminSettingsTypes'

export async function deleteCompanyLogo(): Promise<AdminGeneralSettings> {
  return webApi.delete('/admin/settings/general/company-logo')
}
