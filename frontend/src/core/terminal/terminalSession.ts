/**
 * Keeps a terminal device signed in: challenge, sign, session.
 *
 * 1. `POST terminal-device/challenge` with the bridge's public key returns a
 *    single-use nonce.
 * 2. The bridge signs the nonce with the device's private key.
 * 3. `POST terminal-device/session` with the signature returns a short-lived
 *    terminal access token and the device state. The terminal key from the
 *    bridge goes along as `X-Api-Key`; the backend needs it only to register
 *    an unknown device.
 *
 * The token lives in this closure only, never in storage or a cookie, so it
 * dies with the page. It is renewed by the same three steps about two
 * minutes before it expires, and a 401 on any device call starts a new
 * session at once. Every session request, renewals included, carries what
 * the device is (user agent, screen size, versions and the bridge's device
 * details), so temperature, uptime and display state stay current in
 * Glados; details the bridge cannot give are sent as null, which keeps the
 * previous ones, and never hold up signing in. Failures retry with a growing delay forever, because a
 * wall display has nobody to press a button; that also covers states an
 * admin fixes later, such as terminals switched off or an IP allowlist.
 */
import { ref } from 'vue'
import type { Ref } from 'vue'

import {
  BridgeError,
  getBridgeDeviceDetails,
  getBridgeHealth,
  getBridgeIdentity,
  signWithBridge,
} from './bridgeClient'
import type { BridgeErrorKind } from './bridgeClient'
import {
  requestTerminalChallenge,
  requestTerminalSession,
  terminalErrorCode,
  terminalErrorStatus,
  terminalRetryAfterSeconds,
} from './terminalApi'
import type { TerminalDeviceState, TerminalSessionGrant } from './terminalApi'

export type TerminalSessionErrorKind =
  | BridgeErrorKind
  // An unknown device without a terminal key, or with a wrong or revoked one.
  | 'key_refused'
  // The backend rejected the nonce or signature; a fresh attempt usually works.
  | 'signature_rejected'
  | 'terminals_disabled'
  | 'ip_refused'
  // Too many devices are already waiting for approval.
  | 'pending_limit'
  | 'rate_limited'
  // No answer, a server error, or anything else not listed above.
  | 'unreachable'

export type TerminalSessionStatus = 'idle' | 'authenticating' | 'authenticated' | 'failed'

export interface TerminalSessionState {
  status: TerminalSessionStatus
  error: TerminalSessionErrorKind | null
}

/** What the bridge told about the device, without the terminal key itself. */
export interface TerminalSessionIdentity {
  /** Raw Ed25519 public key, base64url without padding. Not a secret. */
  publicKey: string
  /** Whether the bridge has a terminal key to register an unknown device with. */
  hasTerminalKey: boolean
}

export interface TerminalSessionOptions {
  /** Receives the device state every successful session returns. */
  onDeviceState: (state: TerminalDeviceState) => void
}

export interface TerminalSession {
  readonly state: Readonly<Ref<TerminalSessionState>>
  /**
   * The number of the current or last sign-in attempt since the last
   * successful one, counting renewals; 0 before the first attempt and right
   * after a success.
   */
  readonly attempt: Readonly<Ref<number>>
  /** When the current or last sign-in attempt started, by the device clock. */
  readonly lastAttemptAt: Readonly<Ref<Date | null>>
  /** The device identity of the last attempt that reached the bridge. */
  readonly identity: Readonly<Ref<TerminalSessionIdentity | null>>
  /** Signs in and keeps the token fresh until `stop()`. A no-op while running. */
  start: () => void
  stop: () => void
  /** Drops the token and signs in again now, unless a retry is already scheduled. */
  reauthenticate: () => Promise<void>
  /**
   * Runs a device call with the current token. A 401 starts a new session
   * before the error is passed on, so the next call has a fresh token.
   */
  withToken: <T>(call: (token: string) => Promise<T>) => Promise<T>
  /** The current access token, for the live stream's headers. */
  accessToken: () => string | null
}

export class TerminalNotSignedInError extends Error {
  constructor() {
    super('The terminal has no access token yet')
    this.name = 'TerminalNotSignedInError'
  }
}

export const TOKEN_REFRESH_LEAD_MS = 2 * 60 * 1000
export const MIN_REFRESH_DELAY_MS = 30 * 1000
// What a token is assumed to live for when the device clock disagrees with
// the server's expires_at so much that the difference makes no sense.
const FALLBACK_TOKEN_LIFETIME_MS = 15 * 60 * 1000
const MAX_TOKEN_LIFETIME_MS = 60 * 60 * 1000
export const RETRY_DELAYS_MS = [2000, 5000, 10000, 30000, 60000]
const RETRY_JITTER_RATIO = 0.2
const MAX_RETRY_AFTER_MS = 5 * 60 * 1000

// The backend's error `code` is the domain error's class name. The checks
// below match the words those names are built from, so a 403 still tells a
// switched-off feature from an IP allowlist from a refused key.
const DISABLED_CODE = /Disabled/
const IP_CODE = /Ip(?![a-z])|IP|Allowlist|Address/
const SIGNATURE_CODE = /Nonce|Signature|Challenge/

/** Maps a failed sign-in step to what the device page tells the people in front of it. */
export function classifyTerminalSessionError(error: unknown): TerminalSessionErrorKind {
  if (error instanceof BridgeError) return error.kind
  const status = terminalErrorStatus(error)
  const code = terminalErrorCode(error) ?? ''
  if (status === 429) return 'rate_limited'
  if (status === 409) return 'pending_limit'
  if (status === 403) {
    if (DISABLED_CODE.test(code)) return 'terminals_disabled'
    if (IP_CODE.test(code)) return 'ip_refused'
    return 'key_refused'
  }
  if (status === 401) return SIGNATURE_CODE.test(code) ? 'signature_rejected' : 'key_refused'
  return 'unreachable'
}

function positiveOrNull(value: number | undefined): number | null {
  return typeof value === 'number' && value > 0 ? value : null
}

function deviceTelemetry(bridgeVersion: string | null) {
  const screen = typeof window !== 'undefined' ? window.screen : undefined
  return {
    user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
    screen_width: positiveOrNull(screen?.width),
    screen_height: positiveOrNull(screen?.height),
    frontend_version: __APP_VERSION__,
    bridge_version: bridgeVersion,
  }
}

/**
 * How long a fresh token lives, measured against the device clock. A Pi
 * without network time can be far off, so an `expires_at` that lies in the
 * past or implausibly far ahead falls back to the usual lifetime instead of
 * renewing in a tight loop.
 */
function tokenLifetimeMs(expiresAt: string): number {
  const lifetime = Date.parse(expiresAt) - Date.now()
  if (!Number.isFinite(lifetime) || lifetime <= 0 || lifetime > MAX_TOKEN_LIFETIME_MS) {
    return FALLBACK_TOKEN_LIFETIME_MS
  }
  return lifetime
}

export function createTerminalSession(options: TerminalSessionOptions): TerminalSession {
  const state = ref<TerminalSessionState>({ status: 'idle', error: null })
  const attemptNumber = ref(0)
  const lastAttemptAt = ref<Date | null>(null)
  const identity = ref<TerminalSessionIdentity | null>(null)

  let token: string | null = null
  // Local clock time the token is renewed by; see tokenLifetimeMs.
  let tokenValidUntil = 0
  let running = false
  let runToken = 0
  // Position in the retry backoff, separate from the attempt counter shown on screen.
  let backoffStep = 0
  let timer: ReturnType<typeof setTimeout> | null = null
  let retryPending = false
  let inFlight: Promise<void> | null = null
  let bridgeVersion: string | null = null

  function clearTimer(): void {
    if (timer) clearTimeout(timer)
    timer = null
    retryPending = false
  }

  function schedule(delayMs: number, run: number, isRetry: boolean): void {
    clearTimer()
    retryPending = isRetry
    timer = setTimeout(() => {
      timer = null
      retryPending = false
      if (run === runToken) void authenticate()
    }, delayMs)
  }

  function hasUsableToken(): boolean {
    return token !== null && Date.now() < tokenValidUntil
  }

  function retryDelay(error: unknown): number {
    const retryAfter = terminalRetryAfterSeconds(error)
    if (retryAfter !== null) return Math.min(retryAfter * 1000, MAX_RETRY_AFTER_MS)
    const index = Math.min(backoffStep, RETRY_DELAYS_MS.length - 1)
    backoffStep++
    const base = RETRY_DELAYS_MS[index] ?? RETRY_DELAYS_MS[0]!
    return base + (Math.random() * 2 - 1) * base * RETRY_JITTER_RATIO
  }

  async function signIn(): Promise<TerminalSessionGrant> {
    const bridgeIdentity = await getBridgeIdentity()
    identity.value = {
      publicKey: bridgeIdentity.publicKey,
      hasTerminalKey: bridgeIdentity.apiKey !== null,
    }
    // Read while the challenge runs; it resolves to null instead of failing.
    const deviceDetails = getBridgeDeviceDetails()
    const challenge = await requestTerminalChallenge(bridgeIdentity.publicKey)
    const signature = await signWithBridge(challenge.nonce)
    if (!bridgeVersion) bridgeVersion = (await getBridgeHealth())?.version ?? null
    return requestTerminalSession(
      {
        public_key: bridgeIdentity.publicKey,
        nonce: challenge.nonce,
        signature,
        ...deviceTelemetry(bridgeVersion),
        device: await deviceDetails,
      },
      bridgeIdentity.apiKey,
    )
  }

  function authenticate(): Promise<void> {
    if (inFlight) return inFlight
    if (!running) return Promise.resolve()
    const run = runToken
    clearTimer()
    attemptNumber.value++
    lastAttemptAt.value = new Date()
    // A renewal while the old token still works stays invisible.
    if (!hasUsableToken()) state.value = { status: 'authenticating', error: state.value.error }

    const attemptPromise = (async () => {
      try {
        const grant = await signIn()
        if (run !== runToken) return
        const lifetime = tokenLifetimeMs(grant.expires_at)
        token = grant.access_token
        tokenValidUntil = Date.now() + lifetime
        backoffStep = 0
        attemptNumber.value = 0
        state.value = { status: 'authenticated', error: null }
        schedule(Math.max(lifetime - TOKEN_REFRESH_LEAD_MS, MIN_REFRESH_DELAY_MS), run, false)
        options.onDeviceState(grant.state)
      } catch (error) {
        if (run !== runToken) return
        const kind = classifyTerminalSessionError(error)
        if (!hasUsableToken()) {
          token = null
          state.value = { status: 'failed', error: kind }
        }
        schedule(retryDelay(error), run, true)
      }
    })()

    inFlight = attemptPromise
    void attemptPromise.finally(() => {
      if (inFlight === attemptPromise) inFlight = null
    })
    return attemptPromise
  }

  function start(): void {
    if (running) return
    running = true
    runToken++
    backoffStep = 0
    attemptNumber.value = 0
    void authenticate()
  }

  function stop(): void {
    running = false
    runToken++
    clearTimer()
    inFlight = null
    token = null
    tokenValidUntil = 0
    state.value = { status: 'idle', error: null }
  }

  function reauthenticate(): Promise<void> {
    if (!running) return Promise.resolve()
    if (inFlight) return inFlight
    // A failed attempt already waits out its backoff; jumping the queue
    // would turn a refused device into a request storm.
    if (retryPending && !hasUsableToken()) return Promise.resolve()
    token = null
    tokenValidUntil = 0
    return authenticate()
  }

  async function withToken<T>(call: (token: string) => Promise<T>): Promise<T> {
    const used = token
    if (!used) throw new TerminalNotSignedInError()
    try {
      return await call(used)
    } catch (error) {
      if (terminalErrorStatus(error) === 401 && token === used) void reauthenticate()
      throw error
    }
  }

  return {
    state,
    attempt: attemptNumber,
    lastAttemptAt,
    identity,
    start,
    stop,
    reauthenticate,
    withToken,
    accessToken: () => token,
  }
}
