import { webApi } from '@/core/api/webRequest'
import type {
  AdminPlanningSettings,
  UpdatePlanningSettingsCommand,
} from '../types/adminSettingsTypes'

export async function updatePlanningSettings(
  cmd: UpdatePlanningSettingsCommand,
): Promise<AdminPlanningSettings> {
  return webApi.put('/admin/settings/planning', { body: cmd })
}
