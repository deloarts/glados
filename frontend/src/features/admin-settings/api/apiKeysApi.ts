import { webApi } from '@/core/api/webRequest'
import { createTokenApi } from '@/shared/api/createTokenApi'
import type { CreatedToken } from '@/shared/types/tokenTypes'
import type { TerminalKeyCreateRequest } from '../types/terminalKeyTypes'

export const apiKeysApi = createTokenApi('/admin/api-keys')

/**
 * Creates a terminal key, an API key whose service account holds exactly the
 * permission to connect terminals. It has no permission picker, so the body
 * carries only the name and the optional expiry.
 */
export async function createTerminalKey(cmd: TerminalKeyCreateRequest): Promise<CreatedToken> {
  const created = await webApi.post('/admin/api-keys/terminal', { body: cmd })
  return { ...created, secret: created.key }
}
