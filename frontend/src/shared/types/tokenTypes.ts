/**
 * Shared shape for API keys and personal access tokens (PAT), both backends
 * expose an identical list/create/revoke/usage-log surface, just at
 * different base paths and with a differently-named raw secret field on
 * create ("key" for API keys, "token" for PATs). See createTokenApi.ts,
 * which normalizes that one difference away. Each type here is the part
 * both generated schemas share.
 */
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

/**
 * A PAT row, plus who created it and which kind of key it is on an API key
 * row (PATs are always self-created and have no kind).
 */
export type TokenSummary = Schemas['PatResult'] &
  Partial<Pick<Schemas['ApiKeyResult'], 'created_by_id' | 'kind'>>

/** Returned only by the create call, the single moment the secret is visible. */
export type CreatedToken = TokenSummary & {
  secret: string
}

/** The API key and PAT create bodies are identical. expires_in_days null never expires. */
/**
 * A PAT is created with the current password, an API key without one (see
 * TokenApi.requiresPassword).
 */
export type CreateTokenCommand = Schemas['ApiKeyCreateRequest'] & { password?: string }

/** The API key and PAT list routes take the same query. */
export type TokenFilterParams = QueryOf<'/admin/api-keys'>
export type TokenSortBy = NonNullable<TokenFilterParams['order_by']>
export type TokenSortDir = NonNullable<TokenFilterParams['order_dir']>

/** "never" has no expiry, "expired" is past it, "active" expires later. */
export type TokenExpiryFilter = NonNullable<TokenFilterParams['expiry']>

/** A usage log row without the key or PAT id it belongs to. */
export type TokenUsageLogEntry = Omit<Schemas['ApiKeyUsageLogEntryResult'], 'key_id'>

export type RevokeAllTokensResult = Schemas['RevokeAllApiKeysResult']
