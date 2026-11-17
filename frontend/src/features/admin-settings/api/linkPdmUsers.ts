import { webApi } from '@/core/api/webRequest'
import type { LinkPdmUsersCommand } from '../types/adminSettingsTypes'

/**
 * Saves the PDM user to Glados user links confirmed in the PDM user
 * reconciliation dialog; a null `user_id` unlinks.
 */
export async function linkPdmUsers(cmd: LinkPdmUsersCommand): Promise<void> {
  await webApi.post('/admin/settings/pdm/users/link', { body: cmd })
}
