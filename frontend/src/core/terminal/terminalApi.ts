/**
 * HTTP calls of a terminal device to `/api/v1/web/terminal-device`.
 *
 * Deliberately its own axios instance instead of the app's client in
 * `core/api`: a device has no web session, sends its short-lived terminal
 * token as a Bearer header, and must never run the session client's
 * interceptors, whose 401 handling expires the web session and sends the
 * browser to the login page. Without credentials, so a session cookie the
 * browser may hold never authenticates a device call.
 */
import axios from 'axios'

import type { Schemas } from '@/core/api/generated'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

export const TERMINAL_DEVICE_BASE_URL = `${API_ROOT}/api/v1/web/terminal-device`
export const TERMINAL_LIVE_URL = `${TERMINAL_DEVICE_BASE_URL}/live`

const REQUEST_TIMEOUT_MS = 15000

export type TerminalChallenge = Schemas['TerminalChallengeResponse']
export type TerminalSessionBody = Schemas['TerminalSessionRequest']
export type TerminalSessionGrant = Schemas['TerminalSessionResponse']
export type TerminalDeviceState = Schemas['TerminalDeviceStateResponse']
export type InfoscreenFeed = Schemas['InfoscreenFeedResponse']

export const terminalHttp = axios.create({
  baseURL: TERMINAL_DEVICE_BASE_URL,
  withCredentials: false,
  timeout: REQUEST_TIMEOUT_MS,
})

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

/** Asks for a single-use nonce for the device's public key. */
export async function requestTerminalChallenge(publicKey: string): Promise<TerminalChallenge> {
  const response = await terminalHttp.post<TerminalChallenge>('/challenge', {
    public_key: publicKey,
  })
  return response.data
}

/**
 * Trades the signed nonce for a terminal access token. The terminal key goes
 * along when the bridge has one; the backend needs it only to register a
 * device it does not know yet.
 */
export async function requestTerminalSession(
  body: TerminalSessionBody,
  apiKey: string | null,
): Promise<TerminalSessionGrant> {
  const response = await terminalHttp.post<TerminalSessionGrant>('/session', body, {
    headers: apiKey ? { 'X-Api-Key': apiKey } : {},
  })
  return response.data
}

export async function getTerminalDeviceState(token: string): Promise<TerminalDeviceState> {
  const response = await terminalHttp.get<TerminalDeviceState>('/state', {
    headers: bearer(token),
  })
  return response.data
}

export async function getTerminalDeviceFeed(token: string): Promise<InfoscreenFeed> {
  const response = await terminalHttp.get<InfoscreenFeed>('/feed', { headers: bearer(token) })
  return response.data
}

/** The status of a failed device call, or null when no response came back. */
export function terminalErrorStatus(error: unknown): number | null {
  return axios.isAxiosError(error) ? (error.response?.status ?? null) : null
}

/** The domain error class name the backend puts in `code`, when there is one. */
export function terminalErrorCode(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null
  const data: unknown = error.response?.data
  if (!data || typeof data !== 'object') return null
  const code = (data as { code?: unknown }).code
  return typeof code === 'string' ? code : null
}

/** Seconds from a 429's `Retry-After` header, or null. */
export function terminalRetryAfterSeconds(error: unknown): number | null {
  if (!axios.isAxiosError(error)) return null
  const header: unknown = error.response?.headers?.['retry-after']
  const seconds = Number(header)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null
}
