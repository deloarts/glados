import { BRIDGE_URL } from '@/core/terminal/bridgeClient'
import type { TerminalDeviceState } from '@/core/terminal/terminalApi'
import type {
  TerminalSessionErrorKind,
  TerminalSessionIdentity,
} from '@/core/terminal/terminalSession'

import { SIGN_IN_STEPS } from '../composables/useInfoscreenRuntime'
import type {
  InfoscreenRuntimePhase,
  SignInStep,
  SignInStepId,
} from '../composables/useInfoscreenRuntime'
import { clockParts } from './infoscreenFormat'

// What every waiting screen of a wall display shows: a status code, a plain
// title and sentence, the sign-in steps with the one that stopped, what to
// check, and a footer with the retry attempt, the device and the build. It
// is built from the runtime alone, so whoever stands in front of the
// display can tell what is wrong without a laptop.

type Translate = (key: string, params?: Record<string, unknown>) => string

/** Which waiting screen is shown; also the key of its copy. */
export type SignInReportState =
  | 'starting'
  | 'bridgeMissing'
  | 'identityUnavailable'
  | 'originRefused'
  | 'unreachable'
  | 'rateLimited'
  | 'signatureRejected'
  | 'keyRefused'
  | 'pendingLimit'
  | 'terminalsDisabled'
  | 'ipRefused'
  | 'pending'
  | 'unassigned'
  | 'revoked'

export type SignInReportTone = 'run' | 'wait' | 'warn' | 'fail'

export type SignInReportStepState = 'ok' | 'failed' | 'waiting' | 'running' | 'idle'

export interface SignInReportStep {
  id: SignInStepId
  label: string
  value: string
  result: string
  state: SignInReportStepState
}

export interface SignInReport {
  state: SignInReportState
  code: string
  tone: SignInReportTone
  title: string
  text: string
  hint: string | null
  steps: SignInReportStep[]
  footer: {
    status: string
    /** False while the device keeps failing, which colours the status dot. */
    healthy: boolean
    device: string
    build: string
  }
}

export interface SignInReportInput {
  phase: InfoscreenRuntimePhase
  sessionError: TerminalSessionErrorKind | null
  signInStep: SignInStep
  deviceState: TerminalDeviceState | null
  identity: TerminalSessionIdentity | null
  attempt: number
  lastAttemptAt: Date | null
  /** The origin the page was opened from, which is the Glados server. */
  origin: string
  version: string
}

const CODES: Record<SignInReportState, string> = {
  starting: 'STARTING',
  bridgeMissing: 'BRIDGE_MISSING',
  identityUnavailable: 'IDENTITY_UNAVAILABLE',
  originRefused: 'ORIGIN_REFUSED',
  unreachable: 'UNREACHABLE',
  rateLimited: 'RATE_LIMITED',
  signatureRejected: 'SIGNATURE_REJECTED',
  keyRefused: 'KEY_REFUSED',
  pendingLimit: 'PENDING_LIMIT',
  terminalsDisabled: 'TERMINALS_DISABLED',
  ipRefused: 'IP_REFUSED',
  pending: 'PENDING_APPROVAL',
  unassigned: 'NO_INFOSCREEN',
  revoked: 'REVOKED',
}

// Failures that usually pass by themselves are a warning, the ones that
// need somebody to change a setting are a failure.
const WARNING_STATES: ReadonlySet<SignInReportState> = new Set([
  'bridgeMissing',
  'unreachable',
  'rateLimited',
  'signatureRejected',
  'revoked',
])

const STEP_KEYS: Record<SignInStepId, string> = {
  bridge: 'bridge',
  device_key: 'deviceKey',
  server: 'server',
  registration: 'registration',
  approval: 'approval',
  infoscreen: 'infoscreen',
}

const BRIDGE_ADDRESS = BRIDGE_URL.replace(/^https?:\/\//, '')
const KEY_HEAD = 7
const KEY_TAIL = 4

function reportStateOf(
  phase: InfoscreenRuntimePhase,
  error: TerminalSessionErrorKind | null,
): SignInReportState {
  switch (phase) {
    case 'bridge_missing':
      return 'bridgeMissing'
    case 'identity_error':
      return error === 'origin_refused' ? 'originRefused' : 'identityUnavailable'
    case 'unreachable':
      if (error === 'rate_limited') return 'rateLimited'
      if (error === 'signature_rejected') return 'signatureRejected'
      return 'unreachable'
    case 'registration_refused':
      return 'keyRefused'
    case 'pending_limit':
      return 'pendingLimit'
    case 'disabled':
      return 'terminalsDisabled'
    case 'ip_refused':
      return 'ipRefused'
    case 'pending':
      return 'pending'
    case 'approved_unassigned':
      return 'unassigned'
    case 'revoked':
      return 'revoked'
    default:
      return 'starting'
  }
}

function toneOf(state: SignInReportState): SignInReportTone {
  if (state === 'starting') return 'run'
  if (state === 'pending' || state === 'unassigned') return 'wait'
  return WARNING_STATES.has(state) ? 'warn' : 'fail'
}

/** A public key short enough for one line, its start and end kept to compare. */
export function shortKey(publicKey: string): string {
  if (publicKey.length <= KEY_HEAD + KEY_TAIL + 1) return publicKey
  return `${publicKey.slice(0, KEY_HEAD)}…${publicKey.slice(-KEY_TAIL)}`
}

/** A pairing code in two groups of three, as the approve dialog reads it. */
function groupedCode(code: string): string {
  return code.length === 6 ? `${code.slice(0, 3)} ${code.slice(3)}` : code
}

function hostOf(origin: string): string {
  return origin.replace(/^[a-z]+:\/\//, '')
}

function deviceName(input: SignInReportInput, t: Translate): string {
  return input.deviceState?.name || t('infoscreenRuntime.unnamedDisplay')
}

function stepValue(id: SignInStepId, input: SignInReportInput, t: Translate): string {
  const prefix = 'infoscreenRuntime.report.values'
  switch (id) {
    case 'bridge':
      return BRIDGE_ADDRESS
    case 'device_key':
      return input.identity ? shortKey(input.identity.publicKey) : ''
    case 'server':
      return hostOf(input.origin)
    case 'registration':
      if (!input.identity) return ''
      return t(`${prefix}.${input.identity.hasTerminalKey ? 'terminalKey' : 'noTerminalKey'}`)
    case 'approval': {
      const state = input.deviceState
      if (!state) return ''
      if (state.status === 'pending') {
        return state.pairing_code
          ? t(`${prefix}.pairingCode`, { code: groupedCode(state.pairing_code) })
          : ''
      }
      return state.status === 'approved' ? deviceName(input, t) : ''
    }
    default:
      return ''
  }
}

function stepResult(
  id: SignInStepId,
  state: SignInReportStepState,
  reportState: SignInReportState,
  t: Translate,
): string {
  const prefix = 'infoscreenRuntime.report.results'
  switch (state) {
    case 'ok':
      return t(`${prefix}.passed.${STEP_KEYS[id]}`)
    case 'failed':
      return t(`${prefix}.failed.${reportState}`)
    case 'waiting':
      return t(`${prefix}.${id === 'approval' ? 'pending' : 'noneAssigned'}`)
    case 'running':
      return t(`${prefix}.${id === 'infoscreen' ? 'loading' : 'checking'}`)
    default:
      return t(`${prefix}.notChecked`)
  }
}

function stepStates(step: SignInStep): SignInReportStepState[] {
  const at = SIGN_IN_STEPS.indexOf(step.id)
  const current: SignInReportStepState =
    step.state === 'done' ? 'ok' : step.state === 'failed' ? 'failed' : step.state
  return SIGN_IN_STEPS.map((_, index) => {
    if (index < at) return 'ok'
    if (index === at) return current
    return 'idle'
  })
}

function footerStatus(
  state: SignInReportState,
  input: SignInReportInput,
  t: Translate,
): { status: string; healthy: boolean } {
  const prefix = 'infoscreenRuntime.report.footer'
  const attempt = Math.max(input.attempt, 1)
  switch (state) {
    case 'starting':
      return input.deviceState
        ? { status: t(`${prefix}.loading`), healthy: true }
        : { status: t(`${prefix}.attempt`, { attempt }), healthy: true }
    case 'pending':
      return { status: t(`${prefix}.listeningForApproval`), healthy: true }
    case 'unassigned':
    case 'revoked':
      return { status: t(`${prefix}.listeningForChanges`), healthy: true }
    default: {
      const time = input.lastAttemptAt ? lastTryTime(input.lastAttemptAt) : null
      return {
        status: time
          ? t(`${prefix}.retrying`, { attempt, time })
          : t(`${prefix}.retryingNoTime`, { attempt }),
        healthy: false,
      }
    }
  }
}

function lastTryTime(date: Date): string {
  const { hoursMinutes, seconds } = clockParts(date)
  return `${hoursMinutes}:${seconds}`
}

export function buildSignInReport(input: SignInReportInput, t: Translate): SignInReport {
  const state = reportStateOf(input.phase, input.sessionError)
  const copy = `infoscreenRuntime.report.states.${state}`
  const name = deviceName(input, t)
  const host = hostOf(input.origin)
  const params = { address: BRIDGE_ADDRESS, origin: host, originUrl: input.origin, name }
  const states = stepStates(input.signInStep)

  const steps = SIGN_IN_STEPS.map((id, index) => {
    const stepState = states[index] ?? 'idle'
    return {
      id,
      label: t(`infoscreenRuntime.report.steps.${STEP_KEYS[id]}`),
      value: stepState === 'idle' ? '' : stepValue(id, input, t),
      result: stepResult(id, stepState, state, t),
      state: stepState,
    }
  })

  const prefix = 'infoscreenRuntime.report.footer'
  const device = input.deviceState
    ? input.deviceState.name
      ? t(`${prefix}.device`, { name: input.deviceState.name })
      : t(`${prefix}.deviceUnnamed`)
    : t(`${prefix}.deviceUnknown`)

  return {
    state,
    code: CODES[state],
    tone: toneOf(state),
    // The unassigned screen is named after the display, so the right one is
    // found among several on the terminals page.
    title: state === 'unassigned' ? name : t(`${copy}.title`, params),
    text: t(`${copy}.text`, params),
    hint: state === 'starting' || state === 'pending' ? null : t(`${copy}.hint`, params),
    steps,
    footer: {
      ...footerStatus(state, input, t),
      device,
      build: t(`${prefix}.build`, { version: input.version, origin: host }),
    },
  }
}
