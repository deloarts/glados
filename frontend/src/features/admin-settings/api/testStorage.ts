import { webApi } from '@/core/api/webRequest'
import type { UpdateStorageSettingsCommand } from '../types/adminSettingsTypes'

export async function testStorage(cmd: UpdateStorageSettingsCommand): Promise<void> {
  await webApi.post('/admin/settings/storage/test', { body: cmd })
}
