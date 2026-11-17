/**
 * The state machine of a wall display running `/infoscreen`.
 *
 * It signs the device in through the terminal session, follows the device
 * state the backend keeps for it, and loads the assigned screen's feed:
 *
 * - `booting` until the first answer.
 * - `bridge_missing`, `identity_error`, `registration_refused`,
 *   `pending_limit`, `disabled`, `ip_refused`, `unreachable` when signing in
 *   fails. The session keeps retrying, so the page recovers on its own once
 *   the cause is fixed. A failure before the first device state is held back
 *   for a short grace period, or until a second attempt failed too, because
 *   on a booting device the bridge or the network often comes up a moment
 *   after the browser.
 * - `pending` while the device waits for approval and shows its pairing code.
 * - `approved_unassigned` once approved without a screen.
 * - `showing` with a screen assigned.
 * - `revoked` after a revoke; a new session puts the device back to pending
 *   with a fresh code.
 *
 * Changes arrive on the device's own live stream (`terminal-device/live`)
 * and are refetched after a short debounce, with a 60 second poll as the
 * fallback. A reload or identify request, and a new backend version, are
 * acted on only when they change after the page loaded: the first value is
 * the baseline, so an old request never reloads the page in a loop.
 *
 * The display follows the `display_power` Glados decides from the screen's
 * schedule and the terminal's override. The page has the bridge switch it
 * whenever the wanted power changes, and checks on every state it receives
 * that the bridge still agrees, since a restarted bridge forgets what it
 * was asked and a restarted kiosk starts with the display on. The state is
 * refetched when `display_power_changes_at` comes. While the display is
 * off, the feed of the screen shown is not refreshed, but the state polling
 * and the live stream go on, so the display comes back on time. Nothing
 * switches the display before the first state, and while Glados cannot be
 * reached it stays as it is.
 */
import { computed, effectScope, getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import { LiveResource } from '@/core/realtime/resources'
import { SseHttpError, streamSse } from '@/core/realtime/sseClient'
import { parseBackendTimestamp, setDisplayTimezone } from '@/core/utils/dates'
import type { LiveSignal } from '@/core/realtime/types'
import { getBridgeDisplay, setBridgeDisplayPower } from '@/core/terminal/bridgeClient'
import type { BridgeDisplay, BridgeDisplayPower } from '@/core/terminal/bridgeClient'
import {
  getTerminalDeviceFeed,
  getTerminalDeviceState,
  TERMINAL_LIVE_URL,
  terminalErrorStatus,
} from '@/core/terminal/terminalApi'
import type { InfoscreenFeed, TerminalDeviceState } from '@/core/terminal/terminalApi'
import { createTerminalSession, TerminalNotSignedInError } from '@/core/terminal/terminalSession'
import type {
  TerminalSession,
  TerminalSessionErrorKind,
  TerminalSessionIdentity,
} from '@/core/terminal/terminalSession'

export type InfoscreenRuntimePhase =
  | 'booting'
  | 'bridge_missing'
  | 'identity_error'
  | 'registration_refused'
  | 'pending_limit'
  | 'disabled'
  | 'ip_refused'
  | 'unreachable'
  | 'pending'
  | 'approved_unassigned'
  | 'showing'
  | 'revoked'

/** The steps a device goes through from boot to its infoscreen, in order. */
export const SIGN_IN_STEPS = [
  'bridge',
  'device_key',
  'server',
  'registration',
  'approval',
  'infoscreen',
] as const

export type SignInStepId = (typeof SIGN_IN_STEPS)[number]

/**
 * How far the device got: the step it stands at and how that step is going.
 * Every step before it has passed, every step after it is not reached yet.
 */
export interface SignInStep {
  id: SignInStepId
  state: 'running' | 'failed' | 'waiting' | 'done'
}

export interface InfoscreenRuntime {
  phase: ComputedRef<InfoscreenRuntimePhase>
  /**
   * Why signing in failed, for the detail of an error phase. It stays set
   * while the next attempt runs and is null while a failure is held back.
   */
  sessionError: ComputedRef<TerminalSessionErrorKind | null>
  signInStep: ComputedRef<SignInStep>
  /** The session's current or last sign-in attempt since its last success. */
  attempt: Readonly<Ref<number>>
  /** When that attempt started. */
  lastAttemptAt: Readonly<Ref<Date | null>>
  /** The device identity the bridge handed out, without the terminal key. */
  identity: Readonly<Ref<TerminalSessionIdentity | null>>
  deviceState: Readonly<Ref<TerminalDeviceState | null>>
  /** Whether Glados wants the display on; on until the first device state. */
  displayPower: ComputedRef<BridgeDisplayPower>
  feed: Readonly<Ref<InfoscreenFeed | null>>
  /** When the shown feed stopped updating, or null while it is current. */
  staleSince: Readonly<Ref<Date | null>>
  /** True for a few seconds after an identify request. */
  identifying: Readonly<Ref<boolean>>
  start: () => void
  /** Stops every timer and connection for good; a stopped runtime is not restarted. */
  stop: () => void
}

export interface InfoscreenRuntimeOptions {
  /** Reloads the page; replaced in specs. */
  reload?: () => void
}

export const POLL_INTERVAL_MS = 60_000
export const LIVE_DEBOUNCE_MS = 1000
export const IDENTIFY_DURATION_MS = 10_000
export const REVOKED_RETRY_DELAYS_MS = [3000, 10_000, 30_000, 60_000]
export const SIGN_IN_GRACE_MS = 5000
// How long after `display_power_changes_at` the state is refetched, so a
// device clock slightly ahead of the server still finds the change made.
export const POWER_CHANGE_MARGIN_MS = 1000
// The longest delay a browser timer takes.
const MAX_TIMER_MS = 2_147_483_647
const LIVE_RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10_000, 30_000]

// Failures that leave the last screen up with its stale badge instead of
// replacing it with a message, because they usually pass by themselves.
const TRANSIENT_ERRORS: ReadonlySet<TerminalSessionErrorKind> = new Set([
  'unreachable',
  'rate_limited',
  'signature_rejected',
  'bridge_missing',
])

const ERROR_PHASES: Record<TerminalSessionErrorKind, InfoscreenRuntimePhase> = {
  bridge_missing: 'bridge_missing',
  identity_unavailable: 'identity_error',
  origin_refused: 'identity_error',
  key_refused: 'registration_refused',
  signature_rejected: 'unreachable',
  terminals_disabled: 'disabled',
  ip_refused: 'ip_refused',
  pending_limit: 'pending_limit',
  rate_limited: 'unreachable',
  unreachable: 'unreachable',
}

// Live topics that change the device state rather than the feed: the
// terminal row itself, the messages to terminals and the default display
// schedule.
const STATE_RESOURCES: ReadonlySet<string> = new Set([
  LiveResource.TERMINALS,
  LiveResource.TERMINAL_BROADCASTS,
  LiveResource.INFOSCREEN_DEFAULTS,
])

// Live topics that change both: the screen's row holds its pages and the
// display schedule its terminal follows.
const STATE_AND_FEED_RESOURCES: ReadonlySet<string> = new Set([LiveResource.INFOSCREENS])

// The step each sign-in failure stops at.
const ERROR_STEPS: Record<TerminalSessionErrorKind, SignInStepId> = {
  bridge_missing: 'bridge',
  identity_unavailable: 'device_key',
  origin_refused: 'device_key',
  unreachable: 'server',
  rate_limited: 'server',
  signature_rejected: 'registration',
  key_refused: 'registration',
  terminals_disabled: 'registration',
  ip_refused: 'registration',
  pending_limit: 'registration',
}

function devicePhaseOf(state: TerminalDeviceState | null): InfoscreenRuntimePhase | null {
  if (!state) return null
  if (state.status === 'pending') return 'pending'
  if (state.status === 'revoked') return 'revoked'
  return state.infoscreen_id === null ? 'approved_unassigned' : 'showing'
}

/**
 * Remembers the first value it sees and reports every later value that
 * differs from the last one, so only a change made after the page loaded
 * acts.
 */
function changeTracker<T>() {
  let seen = false
  let last: T | null = null
  return (value: T | null): boolean => {
    if (!seen) {
      seen = true
      last = value
      return false
    }
    const changed = value !== null && value !== last
    last = value
    return changed
  }
}

export function createInfoscreenRuntime(options: InfoscreenRuntimeOptions = {}): InfoscreenRuntime {
  const reload = options.reload ?? (() => window.location.reload())
  const scope = effectScope(true)

  const deviceState = ref<TerminalDeviceState | null>(null)
  const feed = ref<InfoscreenFeed | null>(null)
  const staleSince = ref<Date | null>(null)
  const identifying = ref(false)
  const graceOver = ref(false)

  let running = false
  let stopped = false
  let feedSequence = 0
  let stateSequence = 0
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let identifyTimer: ReturnType<typeof setTimeout> | null = null
  let revokedTimer: ReturnType<typeof setTimeout> | null = null
  let revokedAttempt = 0
  let liveDebounceTimer: ReturnType<typeof setTimeout> | null = null
  let liveWantsState = false
  let liveWantsFeed = false
  let liveController: AbortController | null = null
  let liveRetryTimer: ReturnType<typeof setTimeout> | null = null
  let liveAttempt = 0
  let liveConnectedBefore = false
  let graceTimer: ReturnType<typeof setTimeout> | null = null
  let powerTimer: ReturnType<typeof setTimeout> | null = null
  // The power change the refetch timer already fired for, so a device clock
  // ahead of the server does not refetch in a loop until the server agrees.
  let powerChangeFired: string | null = null
  // What this page last had the bridge switch to; null before the first
  // switch and after a failed one, so the next state tries again.
  let powerRequested: BridgeDisplayPower | null = null
  let powerSyncRunning = false
  let powerSyncAgain = false

  const reloadChanged = changeTracker<string>()
  const identifyChanged = changeTracker<string>()
  const backendVersionChanged = changeTracker<string>()

  const session: TerminalSession = createTerminalSession({ onDeviceState: applyDeviceState })

  // Created inside the runtime's own detached scope: the first view to use
  // the runtime creates it, and its unmount must not stop these.
  const { devicePhase, lastFailure, sessionError, phase, signInStep, displayPower } = scope.run(() => {
    const devicePhase = computed(() => devicePhaseOf(deviceState.value))
    const displayPower = computed<BridgeDisplayPower>(() => deviceState.value?.display_power ?? 'on')
    // The last failure stays while the next attempt runs, so a failing
    // display does not fall back to its starting screen on every retry.
    const lastFailure = computed(() => {
      const current = session.state.value
      return current.status === 'failed' || current.status === 'authenticating'
        ? current.error
        : null
    })
    const failedAttempts = computed(() => {
      const current = session.state.value
      return current.status === 'failed' ? session.attempt.value : session.attempt.value - 1
    })
    const sessionError = computed(() => {
      const error = lastFailure.value
      if (!error) return null
      if (deviceState.value !== null || graceOver.value || failedAttempts.value >= 2) return error
      return null
    })
    const phase = computed<InfoscreenRuntimePhase>(() => {
      const error = sessionError.value
      const fromDevice = devicePhase.value
      if (error && !(TRANSIENT_ERRORS.has(error) && fromDevice !== null)) return ERROR_PHASES[error]
      return fromDevice ?? 'booting'
    })
    const signInStep = computed<SignInStep>(() => {
      const error = sessionError.value
      const current = phase.value
      if (error && current === ERROR_PHASES[error]) return { id: ERROR_STEPS[error], state: 'failed' }
      switch (current) {
        case 'pending':
          return { id: 'approval', state: 'waiting' }
        case 'revoked':
          return { id: 'approval', state: 'failed' }
        case 'approved_unassigned':
          return { id: 'infoscreen', state: 'waiting' }
        case 'showing':
          return { id: 'infoscreen', state: feed.value ? 'done' : 'running' }
        default:
          return { id: 'bridge', state: 'running' }
      }
    })
    return { devicePhase, lastFailure, sessionError, phase, signInStep, displayPower }
  })!

  function markStale(): void {
    if (!staleSince.value) staleSince.value = new Date()
  }

  // ── Device state ───────────────────────────────────────────────────

  function showIdentify(): void {
    identifying.value = true
    if (identifyTimer) clearTimeout(identifyTimer)
    identifyTimer = setTimeout(() => {
      identifyTimer = null
      identifying.value = false
    }, IDENTIFY_DURATION_MS)
  }

  function scheduleRevokedRetry(): void {
    if (revokedTimer) return
    const index = Math.min(revokedAttempt, REVOKED_RETRY_DELAYS_MS.length - 1)
    revokedAttempt++
    revokedTimer = setTimeout(() => {
      revokedTimer = null
      if (running) void session.reauthenticate()
    }, REVOKED_RETRY_DELAYS_MS[index])
  }

  // ── Display power ──────────────────────────────────────────────────

  // A restarted bridge has forgotten the request, and a restarted kiosk has
  // switched the display back on; either shows as a disagreement.
  function bridgeDisagrees(bridge: BridgeDisplay, wanted: BridgeDisplayPower): boolean {
    return bridge.requestedPower !== wanted || (bridge.power !== null && bridge.power !== wanted)
  }

  /**
   * Brings the display to the wanted power. A change is sent straight away;
   * otherwise the bridge is asked first and only switched when it
   * disagrees. A bridge that does not answer leaves the display as it is
   * until the next state.
   */
  async function syncDisplayPower(): Promise<void> {
    if (powerSyncRunning) {
      powerSyncAgain = true
      return
    }
    powerSyncRunning = true
    try {
      do {
        powerSyncAgain = false
        const wanted = deviceState.value?.display_power
        if (!running || !wanted) return
        if (powerRequested === wanted) {
          const bridge = await getBridgeDisplay()
          if (!running || !bridge || !bridgeDisagrees(bridge, wanted)) continue
        }
        const switched = await setBridgeDisplayPower(wanted)
        powerRequested = switched ? wanted : null
      } while (powerSyncAgain)
    } finally {
      powerSyncRunning = false
    }
  }

  function clearPowerTimer(): void {
    if (powerTimer) clearTimeout(powerTimer)
    powerTimer = null
  }

  /** Refetches the state when the display power is due to change. */
  function schedulePowerRefetch(changesAt: string | null): void {
    clearPowerTimer()
    if (!changesAt || changesAt === powerChangeFired) return
    const due = parseBackendTimestamp(changesAt).getTime()
    if (!Number.isFinite(due)) return
    const delay = Math.min(Math.max(due - Date.now() + POWER_CHANGE_MARGIN_MS, 0), MAX_TIMER_MS)
    powerTimer = setTimeout(() => {
      powerTimer = null
      if (Date.now() >= due) powerChangeFired = changesAt
      void refreshState()
    }, delay)
  }

  function applyDeviceState(next: TerminalDeviceState): void {
    if (!running) return
    const previous = deviceState.value
    deviceState.value = next

    if (reloadChanged(next.reload_requested_at)) {
      reload()
      return
    }
    if (identifyChanged(next.identify_requested_at)) showIdentify()

    if (next.status === 'revoked') {
      scheduleRevokedRetry()
    } else {
      revokedAttempt = 0
    }

    void syncDisplayPower()
    schedulePowerRefetch(next.display_power_changes_at)

    if (devicePhaseOf(next) === 'showing') {
      const screenChanged = previous?.infoscreen_id !== next.infoscreen_id
      const switchedOn = previous?.display_power === 'off' && next.display_power === 'on'
      if (!feed.value || screenChanged || switchedOn) void refreshFeed()
    } else {
      feedSequence++
      feed.value = null
      staleSince.value = null
    }
  }

  function handleDeviceCallError(error: unknown): void {
    if (error instanceof TerminalNotSignedInError) return
    // A 403 means the device lost access (switched off, IP allowlist); a new
    // session tells which. A 401 already started one in withToken.
    if (terminalErrorStatus(error) === 403) void session.reauthenticate()
  }

  async function refreshState(): Promise<void> {
    const sequence = ++stateSequence
    try {
      const next = await session.withToken(getTerminalDeviceState)
      if (sequence === stateSequence) applyDeviceState(next)
    } catch (error) {
      handleDeviceCallError(error)
    }
  }

  // ── Feed ───────────────────────────────────────────────────────────

  // A display that is off keeps the feed it has; the first feed of a screen
  // still loads, so the screen is ready when the display comes back on.
  function feedPaused(): boolean {
    const current = feed.value
    return (
      displayPower.value === 'off' &&
      current !== null &&
      current.infoscreen.id === deviceState.value?.infoscreen_id
    )
  }

  async function refreshFeed(): Promise<void> {
    if (devicePhase.value !== 'showing' || feedPaused()) return
    const sequence = ++feedSequence
    try {
      const next = await session.withToken(getTerminalDeviceFeed)
      if (!running || sequence !== feedSequence) return
      if (backendVersionChanged(next.backend_version)) {
        reload()
        return
      }
      // The device has no host capabilities, so the feed names the tenant
      // timezone every clock, date and time on the wall is drawn in.
      setDisplayTimezone(next.timezone)
      feed.value = next
      staleSince.value = null
    } catch (error) {
      if (!running || sequence !== feedSequence) return
      markStale()
      // Not approved or no screen any more: the state says what instead.
      if (terminalErrorStatus(error) === 409) void refreshState()
      else handleDeviceCallError(error)
    }
  }

  async function refreshAll(): Promise<void> {
    await refreshState()
    await refreshFeed()
  }

  // ── Live stream ────────────────────────────────────────────────────

  function scheduleLiveRefresh(state: boolean, feedToo: boolean): void {
    liveWantsState ||= state
    liveWantsFeed ||= feedToo
    if (liveDebounceTimer) clearTimeout(liveDebounceTimer)
    liveDebounceTimer = setTimeout(() => {
      liveDebounceTimer = null
      const wantsState = liveWantsState
      const wantsFeed = liveWantsFeed
      liveWantsState = false
      liveWantsFeed = false
      void (async () => {
        if (wantsState) await refreshState()
        if (wantsFeed) await refreshFeed()
      })()
    }, LIVE_DEBOUNCE_MS)
  }

  function handleLiveFrame(event: string, data: string): void {
    if (event === 'resync') {
      scheduleLiveRefresh(true, true)
      return
    }
    if (event !== 'signal') return
    let signals: LiveSignal[]
    try {
      signals = JSON.parse(data) as LiveSignal[]
    } catch {
      return
    }
    const touchesTerminal = signals.some(
      (signal) =>
        STATE_RESOURCES.has(signal.resource) || STATE_AND_FEED_RESOURCES.has(signal.resource),
    )
    const touchesFeed = signals.some((signal) => !STATE_RESOURCES.has(signal.resource))
    if (touchesTerminal || touchesFeed) scheduleLiveRefresh(touchesTerminal, touchesFeed)
  }

  function nextLiveDelay(): number {
    const index = Math.min(liveAttempt, LIVE_RECONNECT_DELAYS_MS.length - 1)
    liveAttempt++
    return LIVE_RECONNECT_DELAYS_MS[index] ?? LIVE_RECONNECT_DELAYS_MS[0]!
  }

  function connectLive(): void {
    if (!running || liveController || liveRetryTimer) return
    const token = session.accessToken()
    if (!token) return
    const controller = new AbortController()
    liveController = controller
    streamSse(
      {
        url: TERMINAL_LIVE_URL,
        headers: () => ({ Authorization: `Bearer ${session.accessToken() ?? token}` }),
        onOpen: () => {
          liveAttempt = 0
          // Whatever changed while the stream was down is fetched once.
          if (liveConnectedBefore) scheduleLiveRefresh(true, true)
          liveConnectedBefore = true
        },
        onFrame: (frame) => handleLiveFrame(frame.event, frame.data),
      },
      controller.signal,
    )
      .catch((error: unknown) => {
        if (error instanceof SseHttpError && error.status === 401) void session.reauthenticate()
      })
      .finally(() => {
        if (liveController !== controller) return
        liveController = null
        if (!running) return
        liveRetryTimer = setTimeout(() => {
          liveRetryTimer = null
          connectLive()
        }, nextLiveDelay())
      })
  }

  // ── Lifecycle ──────────────────────────────────────────────────────

  scope.run(() => {
    // The grace for a failure before the first device state starts with
    // that failure and runs once per page load.
    watch(lastFailure, (error) => {
      if (!error || graceOver.value || graceTimer || deviceState.value !== null) return
      graceTimer = setTimeout(() => {
        graceTimer = null
        graceOver.value = true
      }, SIGN_IN_GRACE_MS)
    })
    watch(
      () => session.state.value.status,
      (status) => {
        if (status === 'authenticated') connectLive()
        else if (status === 'failed' && devicePhase.value === 'showing') markStale()
      },
    )
  })

  function start(): void {
    if (running || stopped) return
    running = true
    session.start()
    pollTimer = setInterval(() => void refreshAll(), POLL_INTERVAL_MS)
  }

  function stop(): void {
    running = false
    stopped = true
    session.stop()
    for (const timer of [
      identifyTimer,
      revokedTimer,
      liveDebounceTimer,
      liveRetryTimer,
      graceTimer,
      powerTimer,
    ]) {
      if (timer) clearTimeout(timer)
    }
    if (pollTimer) clearInterval(pollTimer)
    identifyTimer = revokedTimer = liveDebounceTimer = liveRetryTimer = graceTimer = pollTimer = null
    powerTimer = null
    liveController?.abort()
    liveController = null
    scope.stop()
  }

  return {
    phase,
    sessionError,
    signInStep,
    attempt: session.attempt,
    lastAttemptAt: session.lastAttemptAt,
    identity: session.identity,
    deviceState,
    displayPower,
    feed,
    staleSince,
    identifying,
    start,
    stop,
  }
}

// One runtime per page load, shared by the entry and register views, so
// moving between the two keeps the session instead of signing in again.
interface SharedRuntime {
  runtime: InfoscreenRuntime
  users: number
  releaseTimer: ReturnType<typeof setTimeout> | null
}

let shared: SharedRuntime | null = null

// The next view's setup runs around the previous view's unmount, so the last
// release waits a moment before it stops the runtime.
const RELEASE_GRACE_MS = 2000

/**
 * The page's device runtime, started on first use. It stops once no view
 * has used it for a moment.
 */
export function useInfoscreenRuntime(): InfoscreenRuntime {
  if (!shared) {
    shared = { runtime: createInfoscreenRuntime(), users: 0, releaseTimer: null }
    shared.runtime.start()
  }
  const entry = shared
  entry.users++
  if (entry.releaseTimer) {
    clearTimeout(entry.releaseTimer)
    entry.releaseTimer = null
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      entry.users--
      if (entry.users > 0) return
      entry.releaseTimer = setTimeout(() => {
        entry.runtime.stop()
        if (shared === entry) shared = null
      }, RELEASE_GRACE_MS)
    })
  }

  return entry.runtime
}
