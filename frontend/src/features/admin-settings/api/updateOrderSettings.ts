import { webApi } from '@/core/api/webRequest'
import type { AdminOrderSettings, UpdateOrderSettingsCommand } from '../types/adminSettingsTypes'

export async function updateOrderSettings(
  cmd: UpdateOrderSettingsCommand,
): Promise<AdminOrderSettings> {
  return webApi.put('/admin/settings/orders', { body: cmd })
}
