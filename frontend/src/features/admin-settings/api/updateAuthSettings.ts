import { webApi } from '@/core/api/webRequest'
import type { AdminAuthSettings, UpdateAuthSettingsCommand } from '../types/adminSettingsTypes'

export async function updateAuthSettings(
  cmd: UpdateAuthSettingsCommand,
): Promise<AdminAuthSettings> {
  return webApi.put('/admin/settings/auth', { body: cmd })
}
