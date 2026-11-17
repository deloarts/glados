import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AxiosError } from 'axios'
import type { AxiosResponse } from 'axios'

import { BridgeError } from '@/core/terminal/bridgeClient'
import type {
  BridgeDisplay,
  BridgeDisplayPower,
  BridgeIdentity,
} from '@/core/terminal/bridgeClient'
import type { SseClientOptions } from '@/core/realtime/sseClient'
import type {
  InfoscreenFeed,
  TerminalDeviceState,
  TerminalSessionGrant,
} from '@/core/terminal/terminalApi'

const getBridgeIdentity = vi.fn<() => Promise<BridgeIdentity>>()
const getBridgeDisplay = vi.fn<() => Promise<BridgeDisplay | null>>()
const setBridgeDisplayPower = vi.fn<(power: BridgeDisplayPower) => Promise<BridgeDisplay | null>>()

vi.mock('@/core/terminal/bridgeClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/terminal/bridgeClient')>()),
  getBridgeIdentity: () => getBridgeIdentity(),
  signWithBridge: async () => 'sig',
  getBridgeHealth: async () => ({ status: 'ok', version: '0.2.0' }),
  getBridgeDeviceDetails: async () => null,
  getBridgeDisplay: () => getBridgeDisplay(),
  setBridgeDisplayPower: (power: BridgeDisplayPower) => setBridgeDisplayPower(power),
}))

const requestTerminalSession = vi.fn<() => Promise<TerminalSessionGrant>>()
const getTerminalDeviceState = vi.fn<(token: string) => Promise<TerminalDeviceState>>()
const getTerminalDeviceFeed = vi.fn<(token: string) => Promise<InfoscreenFeed>>()

vi.mock('@/core/terminal/terminalApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/terminal/terminalApi')>()),
  requestTerminalChallenge: async () => ({ nonce: 'n', expires_at: new Date().toISOString() }),
  requestTerminalSession: () => requestTerminalSession(),
  getTerminalDeviceState: (token: string) => getTerminalDeviceState(token),
  getTerminalDeviceFeed: (token: string) => getTerminalDeviceFeed(token),
}))

// Each stream stays open until the test ends it, like a real live stream.
interface OpenStream {
  options: SseClientOptions
  end: () => void
}
const streams: OpenStream[] = []

vi.mock('@/core/realtime/sseClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/realtime/sseClient')>()),
  streamSse: (options: SseClientOptions, signal: AbortSignal) =>
    new Promise<void>((resolve) => {
      streams.push({ options, end: resolve })
      signal.addEventListener('abort', () => resolve())
      options.onOpen()
    }),
}))

import {
  createInfoscreenRuntime,
  IDENTIFY_DURATION_MS,
  LIVE_DEBOUNCE_MS,
  POLL_INTERVAL_MS,
  POWER_CHANGE_MARGIN_MS,
  SIGN_IN_GRACE_MS,
} from '../composables/useInfoscreenRuntime'
import type { InfoscreenRuntime } from '../composables/useInfoscreenRuntime'
import { getDisplayTimezone, setDisplayTimezone } from '@/core/utils/dates'
import { deviceStateFixture, feedFixture } from './infoscreenFixtures'

const TOKEN_LIFETIME_MS = 15 * 60 * 1000

let sessionState: TerminalDeviceState
let tokenCounter = 0
// What the fake bridge reports: the display as the last switch left it.
let bridgeDisplay: BridgeDisplay

function httpError(status: number) {
  return new AxiosError('failed', 'ERR_BAD_RESPONSE', undefined, undefined, {
    status,
    data: {},
    headers: {},
  } as AxiosResponse)
}

function signal(resource: string) {
  return { event: 'signal', data: JSON.stringify([{ resource, id: 1, action: 'updated', actor_id: null }]) }
}

describe('useInfoscreenRuntime', () => {
  let runtime: InfoscreenRuntime
  const reload = vi.fn<() => void>()

  async function boot(): Promise<void> {
    runtime = createInfoscreenRuntime({ reload })
    runtime.start()
    await vi.advanceTimersByTimeAsync(0)
  }

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-30T08:00:00Z'))
    streams.length = 0
    tokenCounter = 0
    sessionState = deviceStateFixture()
    getBridgeIdentity.mockResolvedValue({ publicKey: 'pk', apiKey: 'terminal-key' })
    requestTerminalSession.mockImplementation(async () => {
      tokenCounter++
      return {
        access_token: `token-${tokenCounter}`,
        expires_at: new Date(Date.now() + TOKEN_LIFETIME_MS).toISOString(),
        state: structuredClone(sessionState),
      } as TerminalSessionGrant
    })
    getTerminalDeviceState.mockImplementation(async () => structuredClone(sessionState))
    getTerminalDeviceFeed.mockImplementation(async () => feedFixture())
    bridgeDisplay = { power: 'on', requestedPower: null, swayReachable: true, lastError: null }
    getBridgeDisplay.mockImplementation(async () => ({ ...bridgeDisplay }))
    setBridgeDisplayPower.mockImplementation(async (power) => {
      bridgeDisplay = { ...bridgeDisplay, power, requestedPower: power }
      return { ...bridgeDisplay }
    })
  })

  afterEach(() => {
    runtime?.stop()
    vi.useRealTimers()
    setDisplayTimezone(null)
  })

  it('shows the pairing phase for a device waiting for approval', async () => {
    sessionState = deviceStateFixture({ status: 'pending', pairing_code: 'K7M3QX', infoscreen_id: null })
    await boot()

    expect(runtime.phase.value).toBe('pending')
    expect(runtime.deviceState.value?.pairing_code).toBe('K7M3QX')
    expect(getTerminalDeviceFeed).not.toHaveBeenCalled()
  })

  it('shows the neutral page for an approved device without an infoscreen', async () => {
    sessionState = deviceStateFixture({ infoscreen_id: null })
    await boot()

    expect(runtime.phase.value).toBe('approved_unassigned')
    expect(runtime.feed.value).toBeNull()
  })

  it('loads the feed of the assigned infoscreen with the terminal token', async () => {
    await boot()

    expect(runtime.phase.value).toBe('showing')
    expect(getTerminalDeviceFeed).toHaveBeenCalledWith('token-1')
    expect(runtime.feed.value?.infoscreen.name).toBe('Hall 2')
  })

  // The device never loads the host capabilities, so the feed is where it
  // learns the tenant timezone its clocks and dates are drawn in.
  it('draws in the tenant timezone the feed names, not the device zone', async () => {
    getTerminalDeviceFeed.mockImplementation(async () => feedFixture({ timezone: 'Asia/Tokyo' }))
    await boot()

    expect(getDisplayTimezone()).toBe('Asia/Tokyo')
  })

  it('reports a missing bridge and recovers once it answers', async () => {
    getBridgeIdentity.mockRejectedValue(new BridgeError('bridge_missing'))
    await boot()
    await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS)
    expect(runtime.phase.value).toBe('bridge_missing')

    getBridgeIdentity.mockResolvedValue({ publicKey: 'pk', apiKey: null })
    await vi.advanceTimersByTimeAsync(15_000)
    expect(runtime.phase.value).toBe('showing')
  })

  it('names a bridge that refuses the origin as an identity error', async () => {
    getBridgeIdentity.mockRejectedValue(new BridgeError('origin_refused'))
    await boot()
    await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS)

    expect(runtime.phase.value).toBe('identity_error')
    expect(runtime.sessionError.value).toBe('origin_refused')
  })

  it('shows switched-off terminals and refused addresses as their own phases', async () => {
    requestTerminalSession.mockRejectedValue(
      new AxiosError('x', 'ERR', undefined, undefined, {
        status: 403,
        data: { code: 'TerminalsDisabledError' },
        headers: {},
      } as AxiosResponse),
    )
    await boot()
    await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS)
    expect(runtime.phase.value).toBe('disabled')
  })

  it('renews the token before it expires and keeps showing', async () => {
    await boot()
    await vi.advanceTimersByTimeAsync(TOKEN_LIFETIME_MS - 2 * 60 * 1000)

    expect(requestTerminalSession).toHaveBeenCalledTimes(2)
    expect(runtime.phase.value).toBe('showing')

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(getTerminalDeviceState).toHaveBeenLastCalledWith('token-2')
  })

  it('signs in again after a revoke, which puts the device back to pending', async () => {
    await boot()
    sessionState = deviceStateFixture({ status: 'revoked', infoscreen_id: null })
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(runtime.phase.value).toBe('revoked')
    expect(runtime.feed.value).toBeNull()

    sessionState = deviceStateFixture({ status: 'pending', pairing_code: 'NEW234', infoscreen_id: null })
    await vi.advanceTimersByTimeAsync(3000)

    expect(requestTerminalSession).toHaveBeenCalledTimes(2)
    expect(runtime.phase.value).toBe('pending')
    expect(runtime.deviceState.value?.pairing_code).toBe('NEW234')
  })

  it('keeps the last feed and marks it stale when the feed fails', async () => {
    await boot()
    getTerminalDeviceFeed.mockRejectedValue(httpError(500))

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

    expect(runtime.feed.value?.infoscreen.name).toBe('Hall 2')
    expect(runtime.staleSince.value).toEqual(new Date('2026-10-30T08:01:00Z'))

    getTerminalDeviceFeed.mockImplementation(async () => feedFixture())
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(runtime.staleSince.value).toBeNull()
  })

  it('refetches state and feed once after a burst of live signals', async () => {
    await boot()
    expect(streams).toHaveLength(1)
    expect(streams[0]!.options.headers()).toEqual({ Authorization: 'Bearer token-1' })
    getTerminalDeviceFeed.mockClear()
    getTerminalDeviceState.mockClear()

    streams[0]!.options.onFrame(signal('production-lots'))
    streams[0]!.options.onFrame(signal('production-orders'))
    await vi.advanceTimersByTimeAsync(LIVE_DEBOUNCE_MS - 1)
    expect(getTerminalDeviceFeed).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(getTerminalDeviceFeed).toHaveBeenCalledTimes(1)
    expect(getTerminalDeviceState).not.toHaveBeenCalled()

    streams[0]!.options.onFrame(signal('terminals'))
    await vi.advanceTimersByTimeAsync(LIVE_DEBOUNCE_MS)
    expect(getTerminalDeviceState).toHaveBeenCalledTimes(1)
  })

  it('reconnects a dropped live stream and catches up', async () => {
    await boot()
    getTerminalDeviceFeed.mockClear()

    streams[0]!.end()
    await vi.advanceTimersByTimeAsync(1000)
    expect(streams).toHaveLength(2)

    await vi.advanceTimersByTimeAsync(LIVE_DEBOUNCE_MS)
    expect(getTerminalDeviceFeed).toHaveBeenCalledTimes(1)
  })

  it('polls every minute as a fallback', async () => {
    await boot()
    getTerminalDeviceState.mockClear()

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(getTerminalDeviceState).toHaveBeenCalledTimes(1)
  })

  it('reloads when a reload is requested after the page loaded, never for the first value', async () => {
    sessionState = deviceStateFixture({ reload_requested_at: '2026-10-29T10:00:00Z' })
    await boot()
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(reload).not.toHaveBeenCalled()

    sessionState = deviceStateFixture({ reload_requested_at: '2026-10-30T08:01:30Z' })
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('shows the identify overlay for ten seconds when identify is requested', async () => {
    sessionState = deviceStateFixture({ identify_requested_at: '2026-10-29T10:00:00Z' })
    await boot()
    expect(runtime.identifying.value).toBe(false)

    sessionState = deviceStateFixture({ identify_requested_at: '2026-10-30T08:00:30Z' })
    streams[0]!.options.onFrame(signal('terminals'))
    await vi.advanceTimersByTimeAsync(LIVE_DEBOUNCE_MS)
    expect(runtime.identifying.value).toBe(true)

    await vi.advanceTimersByTimeAsync(IDENTIFY_DURATION_MS)
    expect(runtime.identifying.value).toBe(false)
  })

  it('reloads when the backend version changes during the run', async () => {
    await boot()
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(reload).not.toHaveBeenCalled()

    getTerminalDeviceFeed.mockImplementation(async () => feedFixture({ backend_version: '1.5.0' }))
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('signs in again when a device call answers 401', async () => {
    await boot()
    getTerminalDeviceState.mockRejectedValueOnce(httpError(401))

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

    expect(requestTerminalSession).toHaveBeenCalledTimes(2)
    expect(runtime.phase.value).toBe('showing')
  })

  describe('the starting screen', () => {
    it('holds a failure before the first device state back during the grace period', async () => {
      // The first retry comes after about two seconds and finds the bridge up.
      getBridgeIdentity.mockRejectedValueOnce(new BridgeError('bridge_missing'))
      await boot()

      expect(runtime.phase.value).toBe('booting')
      expect(runtime.sessionError.value).toBeNull()
      expect(runtime.signInStep.value).toEqual({ id: 'bridge', state: 'running' })

      await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS)
      expect(runtime.phase.value).toBe('showing')
    })

    it('shows a failure that lasts beyond the grace period', async () => {
      requestTerminalSession.mockRejectedValue(httpError(401))
      // A long backoff, so only the grace can end the wait.
      requestTerminalSession.mockRejectedValueOnce(
        new AxiosError('x', 'ERR', undefined, undefined, {
          status: 429,
          data: {},
          headers: { 'retry-after': '60' },
        } as unknown as AxiosResponse),
      )
      await boot()
      await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS - 1)
      expect(runtime.phase.value).toBe('booting')

      await vi.advanceTimersByTimeAsync(1)
      expect(runtime.phase.value).toBe('unreachable')
      expect(runtime.sessionError.value).toBe('rate_limited')
      expect(runtime.signInStep.value).toEqual({ id: 'server', state: 'failed' })
    })

    it('shows the failure at once when the second attempt fails too', async () => {
      requestTerminalSession.mockRejectedValue(httpError(401))
      await boot()
      expect(runtime.phase.value).toBe('booting')
      expect(runtime.attempt.value).toBe(1)

      // The first retry comes after at most 2.4 seconds, inside the grace.
      await vi.advanceTimersByTimeAsync(2500)
      expect(runtime.attempt.value).toBe(2)
      expect(runtime.phase.value).toBe('registration_refused')
      expect(runtime.signInStep.value).toEqual({ id: 'registration', state: 'failed' })
    })

    it('keeps showing the failure while the next attempt runs', async () => {
      let release: () => void = () => {}
      requestTerminalSession.mockRejectedValue(httpError(401))
      await boot()
      await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS)
      expect(runtime.phase.value).toBe('registration_refused')

      getBridgeIdentity.mockImplementation(
        () =>
          new Promise((resolve) => {
            release = () => resolve({ publicKey: 'pk', apiKey: 'terminal-key' })
          }),
      )
      await vi.advanceTimersByTimeAsync(15_000)
      expect(runtime.phase.value).toBe('registration_refused')
      release()
    })

    it('tells the attempt, when it started and the device identity', async () => {
      requestTerminalSession.mockRejectedValue(httpError(401))
      await boot()

      expect(runtime.attempt.value).toBe(1)
      expect(runtime.lastAttemptAt.value).toEqual(new Date('2026-10-30T08:00:00Z'))
      expect(runtime.identity.value).toEqual({ publicKey: 'pk', hasTerminalKey: true })
    })

    it('marks the step a device waits at once it has a state', async () => {
      sessionState = deviceStateFixture({ status: 'pending', pairing_code: 'K7M3QX', infoscreen_id: null })
      await boot()
      expect(runtime.signInStep.value).toEqual({ id: 'approval', state: 'waiting' })

      sessionState = deviceStateFixture({ infoscreen_id: null })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      expect(runtime.signInStep.value).toEqual({ id: 'infoscreen', state: 'waiting' })
    })

    it('loads the screen as the last step before it is shown', async () => {
      let deliver: () => void = () => {}
      getTerminalDeviceFeed.mockImplementation(
        () =>
          new Promise((resolve) => {
            deliver = () => resolve(feedFixture())
          }),
      )
      await boot()

      expect(runtime.phase.value).toBe('showing')
      expect(runtime.signInStep.value).toEqual({ id: 'infoscreen', state: 'running' })

      deliver()
      await vi.advanceTimersByTimeAsync(0)
      expect(runtime.signInStep.value).toEqual({ id: 'infoscreen', state: 'done' })
    })

    it('shows a revoked device at the approval step', async () => {
      sessionState = deviceStateFixture({ status: 'revoked', infoscreen_id: null })
      await boot()

      expect(runtime.phase.value).toBe('revoked')
      expect(runtime.signInStep.value).toEqual({ id: 'approval', state: 'failed' })
    })
  })

  it('refetches the state, not the feed, on a message to terminals', async () => {
    await boot()
    getTerminalDeviceFeed.mockClear()
    getTerminalDeviceState.mockClear()

    streams[0]!.options.onFrame(signal('terminal-broadcasts'))
    await vi.advanceTimersByTimeAsync(LIVE_DEBOUNCE_MS)

    expect(getTerminalDeviceState).toHaveBeenCalledTimes(1)
    expect(getTerminalDeviceFeed).not.toHaveBeenCalled()
  })

  describe('display power', () => {
    it('has the bridge switch the display on the first state and on every change', async () => {
      await boot()
      expect(setBridgeDisplayPower.mock.calls).toEqual([['on']])
      expect(runtime.displayPower.value).toBe('on')

      sessionState = deviceStateFixture({ display_power: 'off' })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      expect(setBridgeDisplayPower.mock.calls).toEqual([['on'], ['off']])
      expect(runtime.displayPower.value).toBe('off')

      sessionState = deviceStateFixture({ display_power: 'on' })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      expect(setBridgeDisplayPower.mock.calls).toEqual([['on'], ['off'], ['on']])
    })

    it('only checks with the bridge while the wanted power stays the same', async () => {
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      setBridgeDisplayPower.mockClear()
      getBridgeDisplay.mockClear()

      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

      expect(getBridgeDisplay).toHaveBeenCalledTimes(1)
      expect(setBridgeDisplayPower).not.toHaveBeenCalled()
    })

    it('switches again after the bridge restarted and forgot the request', async () => {
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      setBridgeDisplayPower.mockClear()

      bridgeDisplay = { ...bridgeDisplay, requestedPower: null }
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

      expect(setBridgeDisplayPower.mock.calls).toEqual([['off']])
    })

    it('switches off again after the kiosk restarted with the display on', async () => {
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      setBridgeDisplayPower.mockClear()

      bridgeDisplay = { ...bridgeDisplay, power: 'on' }
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

      expect(setBridgeDisplayPower.mock.calls).toEqual([['off']])
    })

    it('tries a switch the bridge could not make again with the next state', async () => {
      setBridgeDisplayPower.mockResolvedValueOnce(null)
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      expect(setBridgeDisplayPower).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

      expect(setBridgeDisplayPower.mock.calls).toEqual([['off'], ['off']])
    })

    it('leaves the display alone before the first state', async () => {
      requestTerminalSession.mockRejectedValue(httpError(500))
      await boot()
      await vi.advanceTimersByTimeAsync(SIGN_IN_GRACE_MS)

      expect(setBridgeDisplayPower).not.toHaveBeenCalled()
      expect(getBridgeDisplay).not.toHaveBeenCalled()
    })

    it('keeps the display as it is while Glados cannot be reached', async () => {
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      setBridgeDisplayPower.mockClear()
      getBridgeDisplay.mockClear()
      getTerminalDeviceState.mockRejectedValue(httpError(503))
      getTerminalDeviceFeed.mockRejectedValue(httpError(503))

      await vi.advanceTimersByTimeAsync(3 * POLL_INTERVAL_MS)

      expect(setBridgeDisplayPower).not.toHaveBeenCalled()
      expect(getBridgeDisplay).not.toHaveBeenCalled()
      expect(runtime.displayPower.value).toBe('off')
    })

    it('refetches the state when the display power is due to change', async () => {
      sessionState = deviceStateFixture({ display_power_changes_at: '2026-10-30T08:00:30Z' })
      await boot()
      getTerminalDeviceState.mockClear()
      sessionState = deviceStateFixture({ display_power: 'off' })

      await vi.advanceTimersByTimeAsync(30_000 + POWER_CHANGE_MARGIN_MS - 1)
      expect(getTerminalDeviceState).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(1)
      expect(getTerminalDeviceState).toHaveBeenCalledTimes(1)
      expect(setBridgeDisplayPower).toHaveBeenLastCalledWith('off')
    })

    it('does not refetch in a loop when the device clock runs ahead of the server', async () => {
      // The server still names the change it already passed by the device clock.
      // A change already due is refetched at once, and only once.
      sessionState = deviceStateFixture({ display_power_changes_at: '2026-10-30T07:59:00Z' })
      await boot()

      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS - 1)

      expect(getTerminalDeviceState).toHaveBeenCalledTimes(1)
    })

    it('pauses feed refreshes while the display is off and catches up when it is on again', async () => {
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      // The first feed of a screen loads, so it is ready when the display comes on.
      expect(getTerminalDeviceFeed).toHaveBeenCalledTimes(1)
      getTerminalDeviceFeed.mockClear()
      getTerminalDeviceState.mockClear()

      streams[0]!.options.onFrame(signal('production-lots'))
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

      expect(getTerminalDeviceFeed).not.toHaveBeenCalled()
      expect(getTerminalDeviceState).toHaveBeenCalledTimes(1)
      expect(streams).toHaveLength(1)

      sessionState = deviceStateFixture({ display_power: 'on' })
      streams[0]!.options.onFrame(signal('terminals'))
      await vi.advanceTimersByTimeAsync(LIVE_DEBOUNCE_MS)

      expect(getTerminalDeviceFeed).toHaveBeenCalledTimes(1)
    })

    it('loads the feed of a new screen even while the display is off', async () => {
      sessionState = deviceStateFixture({ display_power: 'off' })
      await boot()
      getTerminalDeviceFeed.mockClear()
      getTerminalDeviceFeed.mockImplementation(async () =>
        feedFixture({ infoscreen: { ...feedFixture().infoscreen, id: 4, name: 'Hall 3' } }),
      )

      sessionState = deviceStateFixture({ display_power: 'off', infoscreen_id: 4 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

      expect(getTerminalDeviceFeed).toHaveBeenCalled()
      expect(runtime.feed.value?.infoscreen.name).toBe('Hall 3')
    })
  })
})
