import { webApi } from '@/core/api/webRequest'
import type { VerifyLdapConnectionCommand } from '../types/adminSettingsTypes'

/**
 * Probes the directory with the supplied (not-yet-saved) settings.
 *
 * 204 on a successful bind. Rejects with 400 when the directory was reached
 * but refused the credentials, and 503 when it could not be reached at all.
 * The caller keeps the two apart, since they need different fixes.
 */
export async function verifyLdapConnection(cmd: VerifyLdapConnectionCommand): Promise<void> {
  await webApi.post('/admin/settings/auth/ldap/test', { body: cmd })
}
