import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AxiosError } from 'axios'
import type { AxiosResponse } from 'axios'

import { BridgeError } from '../bridgeClient'
import type { BridgeDeviceDetails, BridgeHealth, BridgeIdentity } from '../bridgeClient'
import type { TerminalDeviceState, TerminalSessionBody, TerminalSessionGrant } from '../terminalApi'

const getBridgeIdentity = vi.fn<() => Promise<BridgeIdentity>>()
const signWithBridge = vi.fn<(nonce: string) => Promise<string>>()
const getBridgeHealth = vi.fn<() => Promise<BridgeHealth | null>>()
const getBridgeDeviceDetails = vi.fn<() => Promise<BridgeDeviceDetails | null>>()

vi.mock('../bridgeClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../bridgeClient')>()),
  getBridgeIdentity: () => getBridgeIdentity(),
  signWithBridge: (nonce: string) => signWithBridge(nonce),
  getBridgeHealth: () => getBridgeHealth(),
  getBridgeDeviceDetails: () => getBridgeDeviceDetails(),
}))

const requestTerminalChallenge = vi.fn<(publicKey: string) => Promise<{ nonce: string; expires_at: string }>>()
const requestTerminalSession =
  vi.fn<(body: TerminalSessionBody, apiKey: string | null) => Promise<TerminalSessionGrant>>()

vi.mock('../terminalApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../terminalApi')>()),
  requestTerminalChallenge: (publicKey: string) => requestTerminalChallenge(publicKey),
  requestTerminalSession: (body: TerminalSessionBody, apiKey: string | null) =>
    requestTerminalSession(body, apiKey),
}))

import {
  classifyTerminalSessionError,
  createTerminalSession,
  MIN_REFRESH_DELAY_MS,
  RETRY_DELAYS_MS,
  TerminalNotSignedInError,
  TOKEN_REFRESH_LEAD_MS,
} from '../terminalSession'

const NOW = new Date('2026-10-30T08:00:00Z')
const TOKEN_LIFETIME_MS = 15 * 60 * 1000

function deviceState(overrides: Partial<TerminalDeviceState> = {}): TerminalDeviceState {
  return {
    terminal_id: 7,
    status: 'pending',
    mode: 'infoscreen',
    name: null,
    pairing_code: 'ABC234',
    pairing_expires_at: null,
    infoscreen_id: null,
    reload_requested_at: null,
    identify_requested_at: null,
    ...overrides,
  } as TerminalDeviceState
}

let tokenCounter = 0
function grant(): TerminalSessionGrant {
  tokenCounter++
  return {
    access_token: `token-${tokenCounter}`,
    expires_at: new Date(Date.now() + TOKEN_LIFETIME_MS).toISOString(),
    state: deviceState(),
  } as TerminalSessionGrant
}

function httpError(status: number, code: string | null = null, headers: Record<string, string> = {}) {
  return new AxiosError('failed', 'ERR_BAD_RESPONSE', undefined, undefined, {
    status,
    data: code ? { detail: 'x', code } : {},
    headers,
  } as AxiosResponse)
}

// The jitter is ±20 %, so waiting the base delay plus that always passes it.
function withJitter(ms: number): number {
  return Math.ceil(ms * 1.2) + 1
}

describe('terminalSession', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    tokenCounter = 0
    getBridgeIdentity.mockResolvedValue({ publicKey: 'pk', apiKey: 'terminal-key' })
    signWithBridge.mockResolvedValue('sig')
    getBridgeHealth.mockResolvedValue({ status: 'ok', version: '0.2.0' })
    getBridgeDeviceDetails.mockResolvedValue({ computer_model: 'Raspberry Pi 4 Model B', uptime_seconds: 100 })
    requestTerminalChallenge.mockResolvedValue({ nonce: 'nonce-1', expires_at: NOW.toISOString() })
    requestTerminalSession.mockImplementation(async () => grant())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('signs in by challenge, bridge signature and session, with telemetry and the terminal key', async () => {
    const onDeviceState = vi.fn<(state: TerminalDeviceState) => void>()
    const session = createTerminalSession({ onDeviceState })

    session.start()
    await vi.advanceTimersByTimeAsync(0)

    expect(requestTerminalChallenge).toHaveBeenCalledWith('pk')
    expect(signWithBridge).toHaveBeenCalledWith('nonce-1')
    const [body, apiKey] = requestTerminalSession.mock.calls[0]!
    expect(apiKey).toBe('terminal-key')
    expect(body).toMatchObject({
      public_key: 'pk',
      nonce: 'nonce-1',
      signature: 'sig',
      frontend_version: __APP_VERSION__,
      bridge_version: '0.2.0',
    })
    expect(typeof body.user_agent).toBe('string')
    expect(session.state.value).toEqual({ status: 'authenticated', error: null })
    expect(session.accessToken()).toBe('token-1')
    expect(onDeviceState).toHaveBeenCalledWith(expect.objectContaining({ terminal_id: 7 }))
    session.stop()
  })

  it('keeps the token in memory only', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })

    session.start()
    await vi.advanceTimersByTimeAsync(0)

    expect(session.accessToken()).toBe('token-1')
    expect(setItem).not.toHaveBeenCalled()
    expect(document.cookie).not.toContain('token-1')
    session.stop()
  })

  it('renews the token two minutes before it expires', async () => {
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    await vi.advanceTimersByTimeAsync(TOKEN_LIFETIME_MS - TOKEN_REFRESH_LEAD_MS - 1000)
    expect(requestTerminalSession).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1000)
    expect(requestTerminalSession).toHaveBeenCalledTimes(2)
    expect(session.accessToken()).toBe('token-2')
    expect(session.state.value.status).toBe('authenticated')
    session.stop()
  })

  it('sends the device details with the sign-in and again with every renewal', async () => {
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    expect(requestTerminalSession.mock.calls[0]![0].device).toEqual({
      computer_model: 'Raspberry Pi 4 Model B',
      uptime_seconds: 100,
    })

    getBridgeDeviceDetails.mockResolvedValue({ computer_model: 'Raspberry Pi 4 Model B', uptime_seconds: 880 })
    await vi.advanceTimersByTimeAsync(TOKEN_LIFETIME_MS - TOKEN_REFRESH_LEAD_MS)

    expect(requestTerminalSession).toHaveBeenCalledTimes(2)
    expect(getBridgeDeviceDetails).toHaveBeenCalledTimes(2)
    expect(requestTerminalSession.mock.calls[1]![0].device).toMatchObject({ uptime_seconds: 880 })
    session.stop()
  })

  it('signs in without device details when the bridge cannot give them', async () => {
    getBridgeDeviceDetails.mockResolvedValue(null)
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    expect(requestTerminalSession.mock.calls[0]![0].device).toBeNull()
    expect(session.state.value).toEqual({ status: 'authenticated', error: null })
    session.stop()
  })

  it('falls back to the usual lifetime when the device clock is far off', async () => {
    requestTerminalSession.mockImplementation(async () => ({
      ...grant(),
      expires_at: '2020-01-01T00:00:00Z',
    }))
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    await vi.advanceTimersByTimeAsync(MIN_REFRESH_DELAY_MS)
    expect(requestTerminalSession).toHaveBeenCalledTimes(1)
    session.stop()
  })

  it('reports a missing bridge and retries until the bridge answers', async () => {
    getBridgeIdentity.mockRejectedValue(new BridgeError('bridge_missing'))
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })

    session.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(session.state.value).toEqual({ status: 'failed', error: 'bridge_missing' })
    expect(requestTerminalChallenge).not.toHaveBeenCalled()

    getBridgeIdentity.mockResolvedValue({ publicKey: 'pk', apiKey: null })
    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[0]!))

    expect(session.state.value.status).toBe('authenticated')
    expect(requestTerminalSession.mock.calls[0]![1]).toBeNull()
    session.stop()
  })

  it('backs off further after each failure', async () => {
    requestTerminalChallenge.mockRejectedValue(httpError(500))
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })

    session.start()
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[0]!))
    expect(requestTerminalChallenge).toHaveBeenCalledTimes(2)

    // The second delay is longer than the first one.
    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[0]!))
    expect(requestTerminalChallenge).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[1]!))
    expect(requestTerminalChallenge).toHaveBeenCalledTimes(3)
    expect(session.state.value).toEqual({ status: 'failed', error: 'unreachable' })
    session.stop()
  })

  it('waits as long as a 429 asks', async () => {
    requestTerminalChallenge.mockRejectedValueOnce(httpError(429, null, { 'retry-after': '20' }))
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })

    session.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(session.state.value.error).toBe('rate_limited')

    await vi.advanceTimersByTimeAsync(19_000)
    expect(requestTerminalChallenge).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(session.state.value.status).toBe('authenticated')
    session.stop()
  })

  it('keeps the old token when a renewal fails while it is still valid', async () => {
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    requestTerminalSession.mockRejectedValueOnce(httpError(503))
    await vi.advanceTimersByTimeAsync(TOKEN_LIFETIME_MS - TOKEN_REFRESH_LEAD_MS)

    expect(session.state.value).toEqual({ status: 'authenticated', error: null })
    expect(session.accessToken()).toBe('token-1')

    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[0]!))
    expect(session.accessToken()).toBe('token-2')
    session.stop()
  })

  it('signs in again when a device call answers 401', async () => {
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    const call = vi.fn<(token: string) => Promise<string>>().mockRejectedValue(httpError(401))
    await expect(session.withToken(call)).rejects.toBeInstanceOf(AxiosError)
    expect(call).toHaveBeenCalledWith('token-1')

    await vi.advanceTimersByTimeAsync(0)
    expect(requestTerminalSession).toHaveBeenCalledTimes(2)
    expect(session.accessToken()).toBe('token-2')
    session.stop()
  })

  it('refuses a device call before the first token', async () => {
    getBridgeIdentity.mockRejectedValue(new BridgeError('bridge_missing'))
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)

    await expect(session.withToken(async () => 'x')).rejects.toBeInstanceOf(TerminalNotSignedInError)
    session.stop()
  })

  it('does nothing after stop', async () => {
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    session.start()
    await vi.advanceTimersByTimeAsync(0)
    session.stop()

    await vi.advanceTimersByTimeAsync(TOKEN_LIFETIME_MS)
    expect(requestTerminalSession).toHaveBeenCalledTimes(1)
    expect(session.state.value.status).toBe('idle')
    expect(session.accessToken()).toBeNull()
  })

  it('counts the attempts since the last success and when the last one started', async () => {
    getBridgeIdentity.mockRejectedValue(new BridgeError('bridge_missing'))
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    expect(session.attempt.value).toBe(0)
    expect(session.lastAttemptAt.value).toBeNull()

    session.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(session.attempt.value).toBe(1)
    expect(session.lastAttemptAt.value).toEqual(NOW)

    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[0]!))
    expect(session.attempt.value).toBe(2)
    expect(session.lastAttemptAt.value!.getTime()).toBeGreaterThan(NOW.getTime())

    getBridgeIdentity.mockResolvedValue({ publicKey: 'pk', apiKey: 'terminal-key' })
    await vi.advanceTimersByTimeAsync(withJitter(RETRY_DELAYS_MS[1]!))
    expect(session.state.value.status).toBe('authenticated')
    expect(session.attempt.value).toBe(0)
    session.stop()
  })

  it('tells the device identity without the terminal key', async () => {
    const session = createTerminalSession({ onDeviceState: vi.fn<(state: TerminalDeviceState) => void>() })
    expect(session.identity.value).toBeNull()

    session.start()
    await vi.advanceTimersByTimeAsync(0)

    expect(session.identity.value).toEqual({ publicKey: 'pk', hasTerminalKey: true })
    expect(JSON.stringify(session.identity.value)).not.toContain('terminal-key')
    session.stop()
  })

  it('classifies the backend refusals', () => {
    expect(classifyTerminalSessionError(new BridgeError('origin_refused'))).toBe('origin_refused')
    expect(classifyTerminalSessionError(httpError(403, 'TerminalsDisabledError'))).toBe(
      'terminals_disabled',
    )
    expect(classifyTerminalSessionError(httpError(403, 'TerminalIpNotAllowedError'))).toBe(
      'ip_refused',
    )
    expect(classifyTerminalSessionError(httpError(403, 'InvalidTerminalKeyError'))).toBe(
      'key_refused',
    )
    expect(classifyTerminalSessionError(httpError(401, 'TerminalKeyRequiredError'))).toBe(
      'key_refused',
    )
    expect(classifyTerminalSessionError(httpError(401, 'InvalidSignatureError'))).toBe(
      'signature_rejected',
    )
    expect(classifyTerminalSessionError(httpError(409))).toBe('pending_limit')
    expect(classifyTerminalSessionError(httpError(429))).toBe('rate_limited')
    expect(classifyTerminalSessionError(new Error('network'))).toBe('unreachable')
  })
})
