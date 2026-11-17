import { describe, expect, it } from 'vitest'

import { calculateSafetyDistance } from '../calculate'
import { hingeOpening, minimumFieldHeight, requiredFieldDepth } from '../devices'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { HINGE_ANGLES, hingeGap } from '../tables'
import type { GuardInputs, ParallelInputs, SafetyDistanceInputs, SafetyDistanceResult } from '../types'

function withTime(t: number, change: (inputs: SafetyDistanceInputs) => void): SafetyDistanceResult {
  const inputs = sampleSafetyDistanceInputs()
  inputs.responseTime.direct = t
  change(inputs)
  return calculateSafetyDistance(inputs)
}

function parallel(overrides: Partial<ParallelInputs>, t = 0.1): SafetyDistanceResult {
  return withTime(t, (inputs) => {
    inputs.mode = 'parallel'
    inputs.parallel = { ...inputs.parallel, ...overrides }
  })
}

function guard(overrides: Partial<GuardInputs>, t: number): SafetyDistanceResult {
  return withTime(t, (inputs) => {
    inputs.mode = 'guard'
    inputs.guard = { ...inputs.guard, ...overrides }
  })
}

function codes(result: SafetyDistanceResult): string[] {
  return result.messages.map((m) => m.code)
}

describe('parallel approach (clause 9)', () => {
  it('E15 to E17: lowest field height from d_e', () => {
    expect(minimumFieldHeight(70)).toBe(300)
    expect(minimumFieldHeight(40)).toBe(0)
    expect(minimumFieldHeight(116)).toBe(990)
  })

  it('E18: a d_e that needs more than 1000 mm cannot be used', () => {
    const result = parallel({ detection: 117, fieldHeight: 1000 })
    expect(result.s).toBeNull()
    expect(codes(result)).toContain('detectionTooCoarse')
  })

  it('E19: S = 1600 · T + 1200 + Z', () => {
    expect(parallel({}, 0.5).s).toBe(2000)
    const withZ = withTime(0.5, (inputs) => {
      inputs.mode = 'parallel'
      inputs.supplement = 100
    })
    expect(withZ.s).toBe(2100)
  })

  it('checks the field height against 15 · (d_e − 50) and 1000 mm, warning above 200 mm', () => {
    expect(codes(parallel({ detection: 70, fieldHeight: 250 }))).toContain('fieldTooLow')
    const high = parallel({ detection: 70, fieldHeight: 300 })
    expect(high.s).not.toBeNull()
    expect(high.messages).toContainEqual({ code: 'fieldAboveCrawlHeight', level: 'warning', params: { limit: 200 } })
    expect(codes(parallel({ fieldHeight: 1001 }))).toContain('fieldTooHigh')
    expect(codes(parallel({ fieldHeight: 200 }))).not.toContain('fieldAboveCrawlHeight')
  })

  it('needs a field depth of 1200 mm, or 900 mm without a foothold when a standing person is detected', () => {
    expect(requiredFieldDepth(100, true)).toBe(1200)
    expect(requiredFieldDepth(70, true)).toBe(1200)
    expect(requiredFieldDepth(69, true)).toBe(900)
    expect(requiredFieldDepth(50, false)).toBe(1200)
    expect(requiredFieldDepth(null, true)).toBe(1200)

    const shallow = parallel({ fieldDepth: 1000, obstacleGap: 100 })
    expect(shallow.s).toBeNull()
    expect(shallow.messages).toContainEqual({ code: 'fieldTooShallow', level: 'error', params: { min: 1200 } })
    expect(parallel({ fieldDepth: 900, obstacleGap: 50, standingDetected: true }).s).not.toBeNull()
    expect(codes(parallel({ fieldDepth: 1200, obstacleGap: 50 }))).toContain('depthReducible')
  })
})

describe('two-hand control (clause 10)', () => {
  it('E21: S = 1600 · T + 550', () => {
    const result = withTime(0.1, (inputs) => (inputs.mode = 'twoHand'))
    expect(result.s).toBeCloseTo(710, 9)
    expect(result.supplement).toBeNull()
    expect(withTime(0.754, (inputs) => (inputs.mode = 'twoHand')).s).toBeCloseTo(1756.4, 9)
  })

  it('checks type and actuator spacing after ISO 13851 without changing S', () => {
    const twoHand = (type: SafetyDistanceInputs['twoHand']['type'], actuatorGap: number | null) =>
      withTime(0.1, (inputs) => {
        inputs.mode = 'twoHand'
        inputs.twoHand = { encroachmentPrevented: false, type, actuatorGap }
      })
    expect(twoHand('I', 300).messages).toContainEqual({ code: 'twoHandTypeI', level: 'warning' })
    expect(twoHand('IIIC', 550).messages).toContainEqual({ code: 'twoHandTypeIIIC', level: 'info' })
    expect(codes(twoHand('IIIC', 550)).filter((c) => c.startsWith('actuatorGap'))).toEqual([])
    expect(codes(twoHand(null, 200))).toContain('actuatorGapOneHand')
    expect(codes(twoHand(null, 400))).toContain('actuatorGapElbow')
    expect(codes(twoHand(null, 650))).toContain('actuatorGapErgonomic')
    expect(twoHand(null, 200).s).toBeCloseTo(710, 9)
    expect(codes(twoHand(null, null)).some((c) => c.startsWith('twoHandType') || c.startsWith('actuatorGap'))).toBe(false)
  })

  it('E22: with encroachment prevented S = max(1600 · T, 100)', () => {
    const prevent = (inputs: SafetyDistanceInputs) => {
      inputs.mode = 'twoHand'
      inputs.twoHand.encroachmentPrevented = true
    }
    expect(withTime(0.05, prevent).s).toBe(100)
    expect(withTime(0.754, prevent).s).toBeCloseTo(1206.4, 9)
  })
})

describe('hold-to-run controls (clause 11)', () => {
  it('E23: hand 1600 · T + 2200, foot 1600 · T + 2500', () => {
    const hand = (inputs: SafetyDistanceInputs) => (inputs.mode = 'holdToRun')
    const foot = (inputs: SafetyDistanceInputs) => {
      inputs.mode = 'holdToRun'
      inputs.holdToRun.actuation = 'foot'
    }
    expect(withTime(0.1, hand).s).toBeCloseTo(2360, 9)
    expect(withTime(0.1, foot).s).toBeCloseTo(2660, 9)
    expect(withTime(0.754, hand).s).toBeCloseTo(3406.4, 9)
    expect(withTime(0.754, foot).s).toBeCloseTo(3706.4, 9)
  })
})

describe('interlocking guards (clause 12)', () => {
  it('without guard locking S = 1600 · T + D_GT, with D_GT from ISO 13857, Table 4', () => {
    expect(guard({ opening: 50, openingShape: 'slot' }, 0.5).s).toBe(1650)
    const square = guard({ opening: 40, openingShape: 'square' }, 0.5)
    expect(square.s).toBe(1000)
    expect(square.steps.find((s) => s.key === 'reachThroughGuard')).toMatchObject({
      value: 200,
      ref: { standard: 'iso13857', clause: '4.2.4.1', table: '4' },
    })
  })

  it('with guard locking only the time the delay does not cover counts', () => {
    const result = guard({ locking: true, unlockDelay: 0.3, opening: 50 }, 0.5)
    expect(result.s).toBeCloseTo(1170, 9)
    expect(result.steps.find((s) => s.key === 'remainingTime')?.value).toBeCloseTo(0.2, 12)
  })

  it('flags a delay of at least T and leaves S = D_GT', () => {
    const result = guard({ locking: true, unlockDelay: 0.3, opening: 50 }, 0.2)
    expect(result.s).toBe(850)
    expect(codes(result)).toContain('unlockDelayCoversT')
  })

  it('reads the gap of a hinged guard as a slot, and needs the opening', () => {
    const result = guard({ openingMethod: 'hinged', guardWidth: 1000, angle: 5, guardThickness: 20 }, 0.5)
    expect(result.steps.find((s) => s.key === 'opening')?.value).toBeCloseTo(67.1557, 4)
    expect(result.steps.find((s) => s.key === 'reachThroughGuard')?.value).toBe(850)
    expect(result.s).toBe(1650)
    const empty = guard({ opening: null }, 0.5)
    expect(empty.s).toBeNull()
    expect(codes(empty)).toContain('missingInputs')
  })

  it('lowers D_GT for a short slot', () => {
    const short = guard({ opening: 25, openingShape: 'slot', slotLength: 60 }, 0.5)
    expect(short.s).toBe(1000)
    expect(short.steps.find((s) => s.key === 'reachThroughGuard')?.note).toEqual({
      code: 'shortSlotReduction',
      level: 'info',
      params: { length: 65, value: 200 },
    })
    expect(guard({ opening: 25, openingShape: 'slot', slotLength: 70 }, 0.5).s).toBe(1650)
  })

  it('needs an own D_GT beyond Table 4 and flags an own value below the table', () => {
    const wide = guard({ opening: 150 }, 0.5)
    expect(wide.s).toBeNull()
    expect(codes(wide)).toContain('guardOpeningBeyondTable')

    const own = guard({ opening: 150, reachThroughOwn: true, reachThrough: 1000 }, 0.5)
    expect(own.s).toBe(1800)
    expect(own.messages).toContainEqual({ code: 'reachThroughOwnValue', level: 'warning' })

    const below = guard({ opening: 50, reachThroughOwn: true, reachThrough: 500 }, 0.5)
    expect(below.s).toBe(1300)
    expect(below.messages).toContainEqual({ code: 'reachThroughOwnBelowTable', level: 'warning', params: { table: 850 } })
    expect(guard({ opening: 50, reachThroughOwn: true, reachThrough: null }, 0.5).s).toBeNull()
  })

  it('computes the opening of a hinged guard and clamps it at zero', () => {
    expect(hingeOpening(1000, 5, 20).e).toBeCloseTo(67.1557, 4)
    expect(hingeOpening(600, 7, 10).e).toBeCloseTo(63.1216, 4)
    expect(hingeOpening(1200, 9, 4).e).toBeCloseTo(183.7214, 4)
    expect(hingeOpening(100, 3, 6)).toMatchObject({ e: 0, clamped: true })
  })

  it('warns when the opening lets other body parts or the whole body through', () => {
    const own = { reachThroughOwn: true, reachThrough: 850 }
    const whole = guard({ openingMethod: 'hinged', guardWidth: 1200, angle: 9, guardThickness: 4, ...own }, 0.5)
    expect(codes(whole)).toContain('openingWholeBody')
    expect(codes(guard({ opening: 150, ...own }, 0.5))).toContain('openingBodyParts')
    expect(codes(guard({ opening: 120, ...own }, 0.5))).not.toContain('openingBodyParts')
    expect(codes(guard({ opening: 200, openingShape: 'square', ...own }, 0.5))).not.toContain('openingWholeBody')
    expect(codes(guard({ opening: 250, openingShape: 'square', ...own }, 0.5))).toContain('openingWholeBody')
    expect(codes(guard({ openingMethod: 'hinged', guardWidth: 100, angle: 3, guardThickness: 6 }, 0.5))).toContain(
      'openingClamped',
    )
  })
})

describe('Table 5, b = G_W · sin ω', () => {
  const rows: Record<number, number[]> = {
    100: [5.2, 7.0, 8.7, 10.5, 12.2, 13.9, 15.6],
    500: [26.2, 34.9, 43.6, 52.3, 60.9, 69.6, 78.2],
    800: [41.9, 55.8, 69.7, 83.6, 97.5, 111.3, 125.1],
    1100: [57.6, 76.7, 95.9, 115.0, 134.1, 153.1, 172.1],
    1500: [78.5, 104.6, 130.7, 156.8, 182.8, 208.8, 234.7],
  }

  for (const [width, values] of Object.entries(rows)) {
    it(`matches the row G_W = ${width} mm`, () => {
      const computed = HINGE_ANGLES.map((angle) => Math.round(hingeGap(Number(width), angle) * 10) / 10)
      expect(computed).toEqual(values)
    })
  }
})
