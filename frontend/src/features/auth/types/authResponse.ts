import type { Schemas } from '@/core/api/generated'

export type TokenResponse = Schemas['TokenResponse']

export type TotpChallengeResponse = Schemas['TOTPChallengeResponse']

/**
 * Credentials were correct, but 2FA is mandatory and not yet enrolled.
 * `username` is included because the setup token cannot fetch it elsewhere.
 */
export type TotpSetupRequiredResponse = Schemas['TOTPSetupRequiredResponse']

export type LoginResponse = TokenResponse | TotpChallengeResponse | TotpSetupRequiredResponse
