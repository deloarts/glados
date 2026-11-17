import { webApi } from '@/core/api/webRequest'
import type { AllAdminSettings } from '../types/adminSettingsTypes'

export async function getAllAdminSettings(): Promise<AllAdminSettings> {
  // The sections narrow loosely generated fields, see AllAdminSettings.
  return webApi.get('/admin/settings/') as Promise<AllAdminSettings>
}
