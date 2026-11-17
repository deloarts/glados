import { describe, it, expect } from 'vitest'

import { i18n } from '@/core/i18n'
import { sizeDrive } from '../engine'
import { emptyDriveSizingInput } from '../model'
import { SAMPLE_SEGMENTS, SAMPLE_SETTINGS } from '@/features/tools/__tests__/fixtures'
import type { DriveSizingInput } from '../model'
import { driveSizingSnapshot } from '../snapshot'
import { summarizeDriveSizing } from '../summary'

const t = (key: string, params?: Record<string, unknown>) => i18n.global.t(key, params ?? {})

function snapshotOf(changes: Partial<DriveSizingInput>): Record<string, unknown> {
  const input: DriveSizingInput = { ...SAMPLE_SETTINGS, segments: [...SAMPLE_SEGMENTS], ...changes }
  return driveSizingSnapshot(input, sizeDrive(input))
}

describe('driveSizingSnapshot', () => {
  it('keeps rounded figures under stable keys', () => {
    const snapshot = snapshotOf({})

    expect(snapshot).toMatchObject({
      setup: { orientation: 'vertical', angleDeg: null, transmission: 'rack', ratio: 12, carriageMassKg: 100, payloadMassKg: 40 },
      ok: true,
      cycleTimeS: 18.467,
      peakTorqueNm: 6.47,
      rmsTorqueNm: 4.914,
      maxSpeedRpm: 1250,
      failedChecks: 0,
      positionMm: { min: 0, max: 1100, end: 0 },
    })
    expect(snapshot.checks).toMatchObject({
      peakTorque: { value: 6.47, limit: 18, utilisationPct: 35.9, status: 'pass', segment: 4 },
      brakeHolding: { value: 12.271, limit: 13, utilisationPct: 94.4, status: 'pass', segment: null },
    })
    expect(snapshot.segments).toHaveLength(SAMPLE_SEGMENTS.length)
    // A snapshot survives a JSON round trip unchanged.
    expect(JSON.parse(JSON.stringify(snapshot))).toEqual(snapshot)
  })

  it('stores the errors instead of figures for incomplete inputs', () => {
    expect(snapshotOf({ ratio: null })).toEqual({
      setup: { orientation: 'vertical', angleDeg: null, transmission: 'rack', ratio: null, carriageMassKg: 100, payloadMassKg: 40 },
      ok: false,
      errors: [{ code: 'required', field: 'ratio' }],
    })
  })
})

describe('summarizeDriveSizing', () => {
  it('names the axis and gives peak and RMS torque with their utilisation', () => {
    // Peak 6.47 Nm of 18 Nm = 35.9 %, RMS 4.914 Nm of 5.98 Nm = 82.2 %
    expect(summarizeDriveSizing(snapshotOf({}), t)).toBe(
      'Vertical axis, 140 kg, i = 12: peak 6.47 Nm (36%), RMS 4.91 Nm (82%), all checks passed',
    )
  })

  it('counts failed checks', () => {
    // RMS 4.914 Nm against a rated 4 Nm fails, and so does the peak against 6 Nm.
    expect(summarizeDriveSizing(snapshotOf({ ratedTorqueNm: 4 }), t)).toMatch(/, one check failed$/)
    expect(summarizeDriveSizing(snapshotOf({ ratedTorqueNm: 4, maxTorqueNm: 6 }), t)).toMatch(/, 2 checks failed$/)
  })

  it('includes the angle of an inclined axis', () => {
    expect(summarizeDriveSizing(snapshotOf({ orientation: 'inclined', angleDeg: 30 }), t)).toMatch(
      /^Inclined axis \(30°\), 140 kg, i = 12: /,
    )
  })

  it('says when the inputs were incomplete', () => {
    expect(summarizeDriveSizing(snapshotOf({ payloadMassKg: null }), t)).toBe('Vertical axis, i = 12: incomplete inputs')
  })

  it('calls a cleared form a new drive sizing', () => {
    const empty = emptyDriveSizingInput()

    expect(summarizeDriveSizing(driveSizingSnapshot(empty, sizeDrive(empty)), t)).toBe(
      'New drive sizing: incomplete inputs',
    )
  })

  it.each([
    [{}],
    [{ setup: 'vertical' }],
    [{ setup: { orientation: 'diagonal' }, ok: true }],
    [{ setup: { orientation: 'vertical' }, ok: true }],
    [{ setup: { orientation: 'vertical' }, ok: true, checks: { peakTorque: { value: 1 } }, failedChecks: 0 }],
    [{ setup: { orientation: 'vertical' }, ok: 'yes' }],
  ])('returns an empty string for an unexpected shape %j', (results) => {
    expect(summarizeDriveSizing(results as Record<string, unknown>, t)).toBe('')
  })
})
