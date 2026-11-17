import { describe, it, expect, beforeEach } from 'vitest'

import { i18n } from '@/core/i18n'
import type { TerminalSessionErrorKind } from '@/core/terminal/terminalSession'

import type { InfoscreenRuntimePhase, SignInStep } from '../composables/useInfoscreenRuntime'
import { buildSignInReport, shortKey } from '../utils/signInReport'
import type { SignInReportInput } from '../utils/signInReport'
import { deviceStateFixture } from './infoscreenFixtures'

const t = (key: string, params?: Record<string, unknown>) => i18n.global.t(key, params ?? {})

function input(overrides: Partial<SignInReportInput> = {}): SignInReportInput {
  return {
    phase: 'booting',
    sessionError: null,
    signInStep: { id: 'bridge', state: 'running' },
    deviceState: null,
    identity: null,
    attempt: 1,
    lastAttemptAt: new Date('2026-10-30T08:00:05Z'),
    origin: 'https://glados.local',
    version: '2.4.0',
    ...overrides,
  }
}

function stepStates(report: ReturnType<typeof buildSignInReport>) {
  return Object.fromEntries(report.steps.map((step) => [step.id, step.state]))
}

// Every sign-in failure with the phase, the step and the code the runtime
// gives it, as the waiting screen has to show it.
const FAILURES: Array<{
  error: TerminalSessionErrorKind
  phase: InfoscreenRuntimePhase
  step: SignInStep['id']
  code: string
  tone: 'warn' | 'fail'
}> = [
  { error: 'bridge_missing', phase: 'bridge_missing', step: 'bridge', code: 'BRIDGE_MISSING', tone: 'warn' },
  { error: 'identity_unavailable', phase: 'identity_error', step: 'device_key', code: 'IDENTITY_UNAVAILABLE', tone: 'fail' },
  { error: 'origin_refused', phase: 'identity_error', step: 'device_key', code: 'ORIGIN_REFUSED', tone: 'fail' },
  { error: 'unreachable', phase: 'unreachable', step: 'server', code: 'UNREACHABLE', tone: 'warn' },
  { error: 'rate_limited', phase: 'unreachable', step: 'server', code: 'RATE_LIMITED', tone: 'warn' },
  { error: 'signature_rejected', phase: 'unreachable', step: 'registration', code: 'SIGNATURE_REJECTED', tone: 'warn' },
  { error: 'key_refused', phase: 'registration_refused', step: 'registration', code: 'KEY_REFUSED', tone: 'fail' },
  { error: 'terminals_disabled', phase: 'disabled', step: 'registration', code: 'TERMINALS_DISABLED', tone: 'fail' },
  { error: 'ip_refused', phase: 'ip_refused', step: 'registration', code: 'IP_REFUSED', tone: 'fail' },
  { error: 'pending_limit', phase: 'pending_limit', step: 'registration', code: 'PENDING_LIMIT', tone: 'fail' },
]

describe('buildSignInReport', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it.each(FAILURES)('marks the $step step as failed for $error', ({ error, phase, step, code, tone }) => {
    const report = buildSignInReport(
      input({ phase, sessionError: error, signInStep: { id: step, state: 'failed' } }),
      t,
    )

    expect(report.code).toBe(code)
    expect(report.tone).toBe(tone)
    const states = report.steps.map((entry) => entry.state)
    const at = report.steps.findIndex((entry) => entry.id === step)
    expect(states[at]).toBe('failed')
    expect(states.slice(0, at).every((state) => state === 'ok')).toBe(true)
    expect(states.slice(at + 1).every((state) => state === 'idle')).toBe(true)
    expect(report.hint).toBeTruthy()
    expect(report.footer.healthy).toBe(false)
  })

  it('names the reason of the failed step and what to check', () => {
    const report = buildSignInReport(
      input({
        phase: 'identity_error',
        sessionError: 'origin_refused',
        signInStep: { id: 'device_key', state: 'failed' },
      }),
      t,
    )

    expect(report.steps[1]!.result).toBe('403 · origin not allowed')
    expect(report.text).toContain('glados.local')
    expect(report.hint).toContain('https://glados.local')
    expect(report.hint).toContain('BRIDGE__ALLOWED_ORIGINS')
  })

  it('shows the retry attempt and the time of the last try in the footer', () => {
    const report = buildSignInReport(
      input({
        phase: 'unreachable',
        sessionError: 'unreachable',
        signInStep: { id: 'server', state: 'failed' },
        attempt: 7,
      }),
      t,
    )

    expect(report.footer.status).toMatch(/^retrying · attempt 7 · last \d{2}:\d{2}:05$/)
    expect(report.footer.device).toBe('device unknown')
    expect(report.footer.build).toBe('web 2.4.0 · glados.local')
  })

  it('shows the starting screen with the first step running and the attempt', () => {
    const report = buildSignInReport(input(), t)

    expect(report.state).toBe('starting')
    expect(report.code).toBe('STARTING')
    expect(report.tone).toBe('run')
    expect(stepStates(report)).toEqual({
      bridge: 'running',
      device_key: 'idle',
      server: 'idle',
      registration: 'idle',
      approval: 'idle',
      infoscreen: 'idle',
    })
    expect(report.hint).toBeNull()
    expect(report.footer).toMatchObject({ status: 'attempt 1', healthy: true })
  })

  it('shows loading the infoscreen as the same starting screen, one step from the end', () => {
    const report = buildSignInReport(
      input({
        phase: 'showing',
        signInStep: { id: 'infoscreen', state: 'running' },
        deviceState: deviceStateFixture({ name: 'Hall 2 Display' }),
        identity: { publicKey: 'Qm9wTzlkZXZpY2VrZXkx4Tc', hasTerminalKey: true },
      }),
      t,
    )

    expect(report.state).toBe('starting')
    expect(report.steps.map((step) => step.state)).toEqual(['ok', 'ok', 'ok', 'ok', 'ok', 'running'])
    expect(report.steps[5]!.result).toBe('loading')
    expect(report.steps[1]!.value).toBe('Qm9wTzl…x4Tc')
    expect(report.steps[3]!.value).toBe('terminal key')
    expect(report.steps[4]!.value).toBe('Hall 2 Display')
    expect(report.footer.status).toBe('loading the infoscreen')
    expect(report.footer.device).toBe('device Hall 2 Display')
  })

  it('shows a pending display at the approval step with its code', () => {
    const report = buildSignInReport(
      input({
        phase: 'pending',
        signInStep: { id: 'approval', state: 'waiting' },
        deviceState: deviceStateFixture({ status: 'pending', name: null, pairing_code: 'K7MQX2' }),
        attempt: 0,
      }),
      t,
    )

    expect(report.code).toBe('PENDING_APPROVAL')
    expect(report.tone).toBe('wait')
    expect(report.title).toBe('Waiting for approval')
    expect(stepStates(report).approval).toBe('waiting')
    expect(report.steps[4]!.value).toBe('code K7M QX2')
    expect(report.steps[4]!.result).toBe('pending')
    expect(stepStates(report).infoscreen).toBe('idle')
    expect(report.hint).toBeNull()
    expect(report.footer).toMatchObject({
      status: 'listening for approval',
      healthy: true,
      device: 'device unnamed',
    })
  })

  it('names an approved display without an infoscreen after itself', () => {
    const report = buildSignInReport(
      input({
        phase: 'approved_unassigned',
        signInStep: { id: 'infoscreen', state: 'waiting' },
        deviceState: deviceStateFixture({ name: 'Hall 2 North', infoscreen_id: null }),
        attempt: 0,
      }),
      t,
    )

    expect(report.code).toBe('NO_INFOSCREEN')
    expect(report.title).toBe('Hall 2 North')
    expect(report.steps.map((step) => step.state)).toEqual(['ok', 'ok', 'ok', 'ok', 'ok', 'waiting'])
    expect(report.steps[5]!.result).toBe('none assigned')
    expect(report.hint).toContain('Hall 2 North')
    expect(report.footer.status).toBe('listening for changes')
  })

  it('writes the waiting screens in German', () => {
    i18n.global.locale.value = 'deAT'

    const report = buildSignInReport(
      input({
        phase: 'pending',
        signInStep: { id: 'approval', state: 'waiting' },
        deviceState: deviceStateFixture({ status: 'pending', pairing_code: 'K7MQX2' }),
      }),
      t,
    )

    expect(report.steps[4]!.label).toBe('Freigabe')
  })
})

describe('shortKey', () => {
  it('keeps the start and the end of a long key', () => {
    expect(shortKey('3Qm9wTzAAAAAAAAAAAAAAAAAAAx4Tc')).toBe('3Qm9wTz…x4Tc')
    expect(shortKey('short')).toBe('short')
  })
})
