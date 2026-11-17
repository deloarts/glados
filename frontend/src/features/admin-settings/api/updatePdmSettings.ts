import { webApi } from '@/core/api/webRequest'
import type { AdminPdmSettings, UpdatePdmSettingsCommand } from '../types/adminSettingsTypes'

export async function updatePdmSettings(
  cmd: UpdatePdmSettingsCommand,
): Promise<AdminPdmSettings> {
  // The folders and required fields are narrowed, see AdminPdmSettings.
  return webApi.put('/admin/settings/pdm', { body: cmd }) as Promise<AdminPdmSettings>
}
