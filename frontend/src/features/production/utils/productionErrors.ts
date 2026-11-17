import { extractApiErrorCode } from '@/core/utils/errors'

/**
 * Translation keys for the production error codes the backend sends, so a
 * refused completion, scrap or reversal reads in the user's language. Codes
 * outside this map fall back to the backend's detail.
 */
export const PRODUCTION_ERROR_KEYS: Readonly<Record<string, string>> = {
  LotOnHoldError: 'production.errors.lotOnHold',
}

/** The translation key for a known production error code, else null. */
export function productionErrorKey(e: unknown): string | null {
  const code = extractApiErrorCode(e)
  return (code && PRODUCTION_ERROR_KEYS[code]) || null
}
