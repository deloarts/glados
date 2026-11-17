import { webApi } from '@/core/api/webRequest'
import type {
  AdminSecuritySettings,
  UpdateSecuritySettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateSecuritySettings(
  cmd: UpdateSecuritySettingsCommand,
): Promise<AdminSecuritySettings> {
  return webApi.put('/admin/settings/security', { body: cmd })
}
