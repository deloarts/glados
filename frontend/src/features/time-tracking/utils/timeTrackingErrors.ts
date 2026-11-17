import { extractApiError, extractApiErrorCode } from '@/core/utils/errors'

/**
 * Translation keys for the time tracking error codes the backend sends, so
 * a failed save, check or fetch reads in the user's language instead of
 * the English detail. Codes outside this map fall back to the detail.
 */
export const TIME_TRACKING_ERROR_KEYS: Readonly<Record<string, string>> = {
  TimeTrackingNotEnabledError: 'timeTracking.errors.notEnabled',
  TimeTrackingCredentialsMissingError: 'timeTracking.errors.credentialsMissing',
  TimeTrackingAuthenticationFailedError: 'timeTracking.errors.authenticationFailed',
  TimeTrackingPermissionDeniedError: 'timeTracking.errors.permissionDenied',
  TimeTrackingCredentialsNotAllowedError: 'timeTracking.errors.credentialsNotAllowed',
  TimeTrackingProviderError: 'timeTracking.errors.provider',
  TimeTrackingUnavailableError: 'timeTracking.errors.unavailable',
  TimeTrackingRateLimitedError: 'timeTracking.errors.rateLimited',
  TimeTrackingUserAlreadyLinkedError: 'timeTracking.errors.userAlreadyLinked',
  TimeTrackingConsentRequiredError: 'timeTracking.errors.consentRequired',
  TimeTrackingPeriodInvalidError: 'timeTracking.errors.periodInvalid',
  TimeTrackingNotConfiguredError: 'timeTracking.errors.notConfigured',
  TimeTrackingBindingChangedError: 'timeTracking.errors.bindingChanged',
  TimeTrackingKeyChangedError: 'timeTracking.errors.keyChanged',
}

/**
 * Codes after which the stored credentials state may have changed on the
 * server, so the cached account should be read again.
 */
const CREDENTIAL_STATE_CODES = new Set([
  'TimeTrackingCredentialsMissingError',
  'TimeTrackingAuthenticationFailedError',
  'TimeTrackingConsentRequiredError',
  'TimeTrackingNotEnabledError',
  'TimeTrackingBindingChangedError',
])

/**
 * The message to show for a failed time tracking request: the translation
 * for a known code, else the backend's detail, else `fallback`.
 */
export function timeTrackingErrorMessage(
  err: unknown,
  t: (key: string) => string,
  fallback: string,
): string {
  const code = extractApiErrorCode(err)
  const key = code ? TIME_TRACKING_ERROR_KEYS[code] : undefined
  if (key) return t(key)
  return extractApiError(err) ?? fallback
}

/** True when the error says the stored credentials are no longer usable. */
export function isCredentialStateError(err: unknown): boolean {
  const code = extractApiErrorCode(err)
  return code !== null && CREDENTIAL_STATE_CODES.has(code)
}
