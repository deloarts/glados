import { describe, expect, it } from 'vitest'

import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { calculateResponseTime, conditionStats } from '../responseTime'
import type { ResponseTimeInputs } from '../types'

// The measured stopping times of the worked example in Annex B, in s.
const COLD = [0.561, 0.553, 0.612, 0.544, 0.553, 0.571, 0.567, 0.583, 0.656, 0.554]
const WARM = [0.663, 0.654, 0.655, 0.651, 0.727, 0.656, 0.678, 0.665, 0.683, 0.714]

function responseTime(overrides: Partial<ResponseTimeInputs>) {
  return calculateResponseTime({ ...sampleSafetyDistanceInputs().responseTime, ...overrides })
}

describe('response time from measurements (Annex B)', () => {
  it('reproduces the worked example: cold 0.679 s, warmed up 0.754 s, T = 0.754 s', () => {
    const cold = conditionStats('cold', COLD)
    expect(cold?.mean).toBeCloseTo(0.5754, 4)
    expect(cold?.sd).toBeCloseTo(0.03438, 5)
    expect(cold?.meanPlus3Sd).toBeCloseTo(0.679, 3)
    expect(cold?.max).toBe(0.656)
    expect(cold?.t).toBeCloseTo(0.679, 3)

    const warm = conditionStats('warm', WARM)
    expect(warm?.mean).toBeCloseTo(0.6746, 4)
    expect(warm?.sd).toBeCloseTo(0.0265, 4)
    expect(warm?.t).toBeCloseTo(0.754, 3)

    const result = responseTime({ method: 'measured', cold: COLD, warm: WARM })
    expect(result.t).toBeCloseTo(0.754, 3)
    expect(result.messages).toEqual([])
    expect(result.steps.map((s) => s.key)).toEqual(['measuredTime', 'responseTime'])
  })

  it('uses the sample standard deviation with n − 1', () => {
    // Population deviation would be 0.0326 for the cold samples.
    expect(conditionStats('cold', COLD)?.sd).toBeCloseTo(0.0344, 4)
  })

  it('takes the highest sample when it exceeds the mean plus three deviations, and drops no outlier', () => {
    const samples = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 2]
    const stats = conditionStats('warm', samples)
    expect(stats?.max).toBe(2)
    expect(stats?.meanPlus3Sd).toBeLessThan(2)
    expect(stats?.t).toBe(2)
  })

  it('adds t_F to the measured time (equation 5)', () => {
    expect(responseTime({ method: 'measured', cold: COLD, warm: WARM, tF: 0.05 }).t).toBeCloseTo(0.804, 3)
  })

  it('warns below ten samples and when a condition is missing', () => {
    const result = responseTime({ method: 'measured', cold: [0.5, 0.52, 0.51], warm: [] })
    expect(result.t).not.toBeNull()
    expect(result.messages).toEqual([
      { code: 'fewSamplesCold', level: 'warning', params: { n: 3, min: 10 } },
      { code: 'missingSamplesWarm', level: 'warning' },
    ])
  })

  it('uses a single sample as it is and gives no time without samples', () => {
    expect(conditionStats('cold', [0.4])).toMatchObject({ n: 1, sd: null, t: 0.4 })
    expect(responseTime({ method: 'measured' }).t).toBeNull()
  })
})

describe('response time from components (equation 3)', () => {
  it('sums the control and machine times and t_F, empty parts counting as zero', () => {
    const result = responseTime({ method: 'components', tI: 0.015, tL: 0.01, tO: 0.005, tD: 0.02, tR: 0.03, tM: 0.12 })
    expect(result.t).toBeCloseTo(0.2, 12)
    expect(result.steps.find((s) => s.key === 'controlTime')?.value).toBeCloseTo(0.03, 12)
    expect(result.steps.find((s) => s.key === 'machineTime')?.value).toBeCloseTo(0.17, 12)
    expect(responseTime({ method: 'components', tM: 0.1, tF: 0.02 }).t).toBeCloseTo(0.12, 12)
  })
})

describe('known response time', () => {
  it('passes the value through and asks for one when empty', () => {
    expect(responseTime({ method: 'direct', direct: 0.25 }).t).toBe(0.25)
    const empty = responseTime({ method: 'direct', direct: null })
    expect(empty.t).toBeNull()
    expect(empty.messages).toEqual([{ code: 'missingResponseTime', level: 'warning' }])
  })
})
