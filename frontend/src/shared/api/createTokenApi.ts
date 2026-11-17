import { webApi, type QueryOf } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type {
  CreatedToken,
  CreateTokenCommand,
  RevokeAllTokensResult,
  TokenFilterParams,
  TokenSummary,
  TokenUsageLogEntry,
} from '../types/tokenTypes'

/** The API key and PAT usage log routes take the same query. */
export type UsageLogParams = QueryOf<'/admin/api-keys/{key_id}/usage-log'>

export interface TokenApi {
  /** Whether create() needs the acting user's current password, false when omitted. */
  requiresPassword?: boolean
  list(params?: TokenFilterParams): Promise<PageResponse<TokenSummary>>
  create(cmd: CreateTokenCommand): Promise<CreatedToken>
  revoke(id: number): Promise<TokenSummary>
  revokeAll(): Promise<RevokeAllTokensResult>
  getUsageLog(id: number, params?: UsageLogParams): Promise<PageResponse<TokenUsageLogEntry>>
}

/** The base paths of the two token surfaces. */
export type TokenBasePath = '/admin/api-keys' | '/users/me/personal-access-tokens'

/**
 * The raw secret is returned under different field names by the two
 * backends (API keys: "key", PATs: "token"), normalized to
 * CreatedToken.secret here so shared components never need to know which
 * feature they're rendering.
 */
function normalizeCreated(data: TokenSummary & { key?: string; token?: string }): CreatedToken {
  const secret = data.key ?? data.token
  if (secret === undefined) {
    throw new Error('Token creation response is missing a secret value.')
  }
  return { ...data, secret }
}

// One client per surface, since the two name their path parameter
// differently (key_id, pat_id) and each route is checked on its own.
const TOKEN_APIS: Record<TokenBasePath, TokenApi> = {
  '/admin/api-keys': {
    requiresPassword: false,
    list: (params) => webApi.get('/admin/api-keys/', { query: params }),
    create: async ({ password: _password, ...cmd }) =>
      normalizeCreated(await webApi.post('/admin/api-keys/', { body: cmd })),
    revoke: (id) => webApi.post('/admin/api-keys/{key_id}/revoke', { path: { key_id: id } }),
    revokeAll: () => webApi.post('/admin/api-keys/revoke-all'),
    getUsageLog: (id, params) =>
      webApi.get('/admin/api-keys/{key_id}/usage-log', { path: { key_id: id }, query: params }),
  },
  '/users/me/personal-access-tokens': {
    requiresPassword: true,
    list: (params) => webApi.get('/users/me/personal-access-tokens/', { query: params }),
    create: async ({ password, ...cmd }) =>
      normalizeCreated(
        await webApi.post('/users/me/personal-access-tokens/', {
          body: { ...cmd, password: password ?? '' },
        }),
      ),
    revoke: (id) =>
      webApi.post('/users/me/personal-access-tokens/{pat_id}/revoke', { path: { pat_id: id } }),
    revokeAll: () => webApi.post('/users/me/personal-access-tokens/revoke-all'),
    getUsageLog: (id, params) =>
      webApi.get('/users/me/personal-access-tokens/{pat_id}/usage-log', {
        path: { pat_id: id },
        query: params,
      }),
  },
}

/** Both API keys and PATs expose an identical REST shape, just at different base paths. */
export function createTokenApi(basePath: TokenBasePath): TokenApi {
  return TOKEN_APIS[basePath]
}
