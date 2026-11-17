import { webApi } from '@/core/api/webRequest'
import type {
  AdminMaintenanceSettings,
  UpdateMaintenanceSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updateMaintenanceSettings(
  cmd: UpdateMaintenanceSettingsCommand,
): Promise<AdminMaintenanceSettings> {
  return webApi.put('/admin/settings/maintenance', { body: cmd })
}
