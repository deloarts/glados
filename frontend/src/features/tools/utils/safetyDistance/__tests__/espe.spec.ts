import { describe, expect, it } from 'vitest'

import { approachSpeedRule } from '../approachSpeed'
import { calculateSafetyDistance } from '../calculate'
import { matchBeamRow, reachThroughDistance, reachUnderDistance } from '../espe'
import { emptySafetyDistanceInputs } from '../inputs'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { lookupByHazardHeight, lookupReachOver, REACH_UNDER, REACH_UNDER_STRUCTURE } from '../tables'
import type { EspeInputs, PathResult, SafetyDistanceResult } from '../types'

// A hazard at 1200 mm behind a field from the floor to 1600 mm: Table 2 gives
// no reach over and the reach under follows the finger formula, so these
// cases isolate the reach through the field.
function espe(overrides: Partial<EspeInputs>, t: number, supplement = 0): SafetyDistanceResult {
  const inputs = sampleSafetyDistanceInputs()
  inputs.responseTime.direct = t
  inputs.supplement = supplement
  inputs.espe = { ...inputs.espe, hazardHeight: 1200, topEdge: 1600, bottomEdge: 0, ...overrides }
  return calculateSafetyDistance(inputs)
}

function path(result: SafetyDistanceResult, name: PathResult['path']): PathResult | undefined {
  return result.paths.find((p) => p.path === name)
}

function codes(result: SafetyDistanceResult): string[] {
  return result.messages.map((m) => m.code)
}

function step(result: SafetyDistanceResult, key: string): number | undefined {
  return result.steps.find((s) => s.key === key)?.value
}

describe('reach through the field (8.3)', () => {
  it('follows the finger, forearm and arm formulas', () => {
    expect(reachThroughDistance(14)).toBe(0)
    expect(reachThroughDistance(10)).toBe(0)
    expect(reachThroughDistance(30)).toBe(128)
    expect(reachThroughDistance(50)).toBe(328)
    expect(reachThroughDistance(80)).toBe(850)
  })

  it('is continuous at 40 mm and jumps to the arm length above 55 mm', () => {
    expect(reachThroughDistance(40)).toBe(208)
    expect(reachThroughDistance(40.5)).toBeCloseTo(214, 9)
    expect(reachThroughDistance(55)).toBe(388)
    expect(reachThroughDistance(55.5)).toBe(850)
  })
})

describe('approach speed rule', () => {
  it('uses 2000 mm/s up to 500 mm, then 1600 mm/s with a 500 mm minimum', () => {
    expect(approachSpeedRule(0.1, 0, 0, { fallback: true, publicArea: false })).toMatchObject({ k: 2000, s: 200 })
    expect(approachSpeedRule(0.03, 0, 0, { fallback: true, publicArea: false })).toMatchObject({ s: 100, floor: 100 })
    expect(approachSpeedRule(0.2, 128, 0, { fallback: true, publicArea: false })).toMatchObject({
      k: 1600,
      sWithHand: 528,
      s: 500,
      floor: 500,
    })
  })

  it('adds 75 mm after the 100 mm minimum where the public may be present', () => {
    expect(approachSpeedRule(0.02, 0, 0, { fallback: true, publicArea: true }).s).toBe(175)
    expect(approachSpeedRule(0.3, 128, 0, { fallback: true, publicArea: true })).toMatchObject({ k: 2000, s: 803 })
  })
})

describe('light curtain fixtures', () => {
  it('E1: d_e 14 mm, T 0.1 s gives 200 mm', () => {
    const result = espe({ detection: 14 }, 0.1)
    expect(step(result, 'reachThrough')).toBe(0)
    expect(result.s).toBe(200)
    expect(result.k).toBe(2000)
  })

  it('E2: a result below 100 mm is raised to 100 mm', () => {
    expect(espe({ detection: 14 }, 0.03).s).toBe(100)
  })

  it('E3: above 500 mm the walking speed applies with a 500 mm minimum', () => {
    const result = espe({ detection: 30 }, 0.2)
    expect(result.s).toBe(500)
    expect(result.k).toBe(1600)
    expect(codes(result)).toContain('walkingSpeedApplies')
  })

  it('E4: d_e 30 mm, T 0.3 s gives 608 mm', () => {
    expect(espe({ detection: 30 }, 0.3).s).toBeCloseTo(608, 9)
  })

  it('E5: d_e 50 mm uses the forearm formula and ends at the 500 mm minimum', () => {
    const result = espe({ detection: 50 }, 0.1)
    expect(step(result, 'reachThrough')).toBe(328)
    expect(result.s).toBe(500)
  })

  it('E7: where the public may be present 75 mm are added and K stays 2000 mm/s', () => {
    const result = espe({ detection: 30, industrial: false }, 0.1)
    expect(result.s).toBe(403)
    const noFallback = espe({ detection: 30, industrial: false }, 0.3)
    expect(noFallback.k).toBe(2000)
    expect(noFallback.s).toBeCloseTo(803, 9)
  })

  it('E8: d_e 80 mm gives the arm length with 1600 mm/s and a warning', () => {
    const result = espe({ detection: 80 }, 0.1)
    expect(result.s).toBeCloseTo(1010, 9)
    expect(result.k).toBe(1600)
    expect(codes(result)).toContain('handNotDetected')
  })

  it('E9: a single beam gives 1600 · T + 1200', () => {
    expect(espe({ device: 'singleBeam' }, 0.2).s).toBeCloseTo(1520, 9)
    expect(espe({ device: 'singleBeam' }, 0.2, 50).s).toBeCloseTo(1570, 9)
  })

  it('E10: reach under; the combined method is larger than the path on its own', () => {
    const result = espe({ detection: 14, bottomEdge: 20 }, 0.1)
    expect(step(result, 'reachUnder')).toBe(160)
    expect(path(result, 'under')).toMatchObject({ k: 1600, s: 320 })
    expect(path(result, 'through')).toMatchObject({ k: 2000, s: 200 })
    expect(result.s).toBe(360)
  })

  it('E11: reach under from Table 3 when d_e + H_DB exceeds 40 mm', () => {
    const result = espe({ detection: 30, bottomEdge: 200, hazardHeight: 500 }, 0.1)
    expect(step(result, 'reachUnder')).toBe(800)
    expect(path(result, 'under')?.s).toBeCloseTo(960, 9)
    expect(result.s).toBeCloseTo(960, 9)
  })

  it('E12: a bottom edge above 300 mm is not permitted', () => {
    const result = espe({ bottomEdge: 350 }, 0.1)
    expect(result.s).toBeNull()
    expect(result.messages).toContainEqual({ code: 'bottomEdgeTooHigh', level: 'error', params: { max: 300 } })
  })

  it('E13: reach over from Table 2 off the grid, then the walking speed', () => {
    const result = espe({ detection: 14, hazardHeight: 1000, topEdge: 1500 }, 0.1)
    expect(step(result, 'reachOver')).toBe(700)
    expect(result.steps.find((s) => s.key === 'reachOver')?.note).toEqual({
      code: 'reachOverColumn',
      level: 'info',
      params: { column: 1400 },
    })
    expect(result.s).toBeCloseTo(860, 9)
  })

  it('a top edge below 900 mm is not covered unless a structure closes the space above', () => {
    const low = espe({ topEdge: 850 }, 0.1)
    expect(low.s).toBeNull()
    expect(codes(low)).toContain('topEdgeTooLow')

    const covered = espe({ topEdge: 850, structureAbove: true, structureTop: 1800 }, 0.1)
    expect(covered.s).toBe(700)
    expect(path(covered, 'over')).toBeUndefined()
    expect(path(covered, 'overStructure')).toMatchObject({ s: 700, k: null })
    expect(codes(covered)).toContain('structureGoverns')
  })

  it('reads D_GO from ISO 13857, Table 2 with the hazard height and the top of the structure', () => {
    const result = espe({ structureAbove: true, structureTop: 1500 }, 0.1)
    const over = result.steps.find((s) => s.key === 'reachOverStructure')
    expect(over?.value).toBe(1100)
    expect(over?.ref).toEqual({ standard: 'iso13857', clause: '4.2.2', table: '2' })
    expect(over?.note).toEqual({ code: 'tableColumn', level: 'info', params: { table: 2, column: 1400 } })
    expect(result.s).toBe(1100)

    const low = espe({ structureAbove: true, structureTop: 1200 }, 0.1)
    expect(codes(low)).toContain('structureTopLow')
    const tooLow = espe({ structureAbove: true, structureTop: 950 }, 0.1)
    expect(tooLow.s).toBeNull()
    expect(codes(tooLow)).toContain('structureTopTooLow')
    expect(espe({ structureAbove: true, structureTop: null }, 0.1).messages).toContainEqual({
      code: 'missingInputs',
      level: 'warning',
    })
  })

  it('E20: a structure below with 120 < H_GB ≤ 180 mm takes D_GU from Table 4', () => {
    const result = espe({ hazardHeight: 900, structureBelow: true, structureGap: 150 }, 0.1)
    expect(step(result, 'reachUnderStructure')).toBe(800)
    expect(result.s).toBe(800)
  })

  it('a structure below reads D_GU up to 120 mm from ISO 13857, Table 4 as a slot and is not covered above 180 mm', () => {
    const slot = espe({ structureBelow: true, structureGap: 100 }, 0.1)
    expect(slot.s).toBe(850)
    expect(slot.steps.find((s) => s.key === 'reachUnderStructure')).toMatchObject({
      value: 850,
      ref: { standard: 'iso13857', clause: '4.2.4.1', table: '4' },
      note: { code: 'gapAsSlot', level: 'info' },
    })
    expect(step(espe({ structureBelow: true, structureGap: 10 }, 0.1), 'reachUnderStructure')).toBe(80)
    expect(step(espe({ structureBelow: true, structureGap: 120 }, 0.1), 'reachUnderStructure')).toBe(850)
    const wide = espe({ structureBelow: true, structureGap: 200 }, 0.1)
    expect(wide.s).toBeNull()
    expect(codes(wide)).toContain('structureGapTooLarge')
  })

  it('reports a bottom edge above the top edge', () => {
    expect(codes(espe({ bottomEdge: 300, topEdge: 300, structureAbove: true, structureTop: 2000 }, 0.1))).toContain(
      'edgesInverted',
    )
  })

  it('adds the supplement Z to every path', () => {
    const result = espe({ detection: 14 }, 0.1, 40)
    expect(result.s).toBe(240)
    expect(path(result, 'under')?.s).toBe(200)
  })
})

describe('restart by the light curtain (8.6)', () => {
  it('E24: raises a result of 148 mm to just above the 150 mm minimum, which S has to exceed', () => {
    const result = espe({ detection: 20, restart: true }, 0.05)
    expect(step(result, 'withHandSpeed')).toBe(148)
    expect(result.s).toBe(150.1)
    expect(result.messages).toContainEqual({
      code: 'restartMinimumApplied',
      level: 'warning',
      params: { min: 150, raised: 150.1 },
    })
    // Exactly the minimum is not more than it.
    expect(espe({ detection: 20, restart: true }, 0.051).s).toBe(150.1)
  })

  it('uses 100 mm for d_e up to 14 mm and keeps K = 2000 mm/s above 500 mm', () => {
    expect(espe({ detection: 14, restart: true }, 0.1).messages).toContainEqual({
      code: 'restartMinimumMet',
      level: 'info',
      params: { min: 100 },
    })
    const long = espe({ detection: 14, restart: true }, 0.3)
    expect(long.k).toBe(2000)
    expect(long.s).toBeCloseTo(600, 9)
  })

  it('is not permitted above d_e 30 mm', () => {
    const result = espe({ detection: 35, restart: true }, 0.1)
    expect(result.s).toBeNull()
    expect(codes(result)).toContain('restartResolution')
  })
})

describe('Table 2 lookup', () => {
  it('reads grid values directly', () => {
    expect(lookupReachOver(1000, 900)).toEqual({ value: 1200, column: 0, rows: [1000], exact: true })
    expect(lookupReachOver(2500, 2000)?.value).toBe(250)
    expect(lookupReachOver(600, 1200)?.value).toBe(550)
  })

  it('E14: takes the larger value of both rows between two hazard heights', () => {
    expect(lookupReachOver(1100, 900)).toEqual({ value: 1200, column: 0, rows: [1000, 1200], exact: false })
    expect(lookupReachOver(1500, 1000)?.value).toBe(1200)
    expect(lookupReachOver(700, 1300)?.value).toBe(500)
  })

  it('reads a top edge between columns in the lower column', () => {
    expect(lookupReachOver(1000, 1500)?.value).toBe(700)
    expect(lookupReachOver(2200, 2399)?.value).toBe(250)
    expect(lookupReachOver(1000, 3000)?.value).toBe(0)
  })

  it('gives nothing below 900 mm and no reach for hazards at 2600 mm or higher', () => {
    expect(lookupReachOver(1000, 899)).toBeNull()
    expect(lookupReachOver(2600, 900)?.value).toBe(0)
    expect(lookupReachOver(3000, 900)?.value).toBe(0)
  })
})

describe('Tables 3 and 4 lookup', () => {
  it('reads Table 3 in the lower row between two heights', () => {
    expect(lookupByHazardHeight(REACH_UNDER, 0).value).toBe(850)
    expect(lookupByHazardHeight(REACH_UNDER, 500)).toEqual({ value: 800, row: 500, exact: true })
    expect(lookupByHazardHeight(REACH_UNDER, 600)).toEqual({ value: 800, row: 500, exact: false })
    expect(lookupByHazardHeight(REACH_UNDER, 1000).value).toBe(450)
    expect(lookupByHazardHeight(REACH_UNDER, 1500).value).toBe(0)
  })

  it('reads Table 4 the same way', () => {
    expect(lookupByHazardHeight(REACH_UNDER_STRUCTURE, 900)).toEqual({ value: 800, row: 800, exact: false })
    expect(lookupByHazardHeight(REACH_UNDER_STRUCTURE, 1000).value).toBe(600)
    expect(lookupByHazardHeight(REACH_UNDER_STRUCTURE, 1300).value).toBe(0)
  })

  it('combines the formula and Table 3 for the reach under', () => {
    expect(reachUnderDistance(14, 20, 0)).toBe(160)
    expect(reachUnderDistance(30, 200, 500)).toBe(800)
    expect(reachUnderDistance(14, 0, 0)).toBe(0)
    expect(reachUnderDistance(14, 301, 0)).toBeNull()
  })
})

describe('multi-beam devices (8.3.5, Annex C)', () => {
  function beams(beamHeights: number[], extra: Partial<EspeInputs> = {}, t = 0.2) {
    return espe({ device: 'multiBeam', beamHeights, ...extra }, t)
  }

  it('gives 1600 · T + 850 where nothing can be reached over the top beam, and recognises a row of Table C.1', () => {
    const result = beams([200, 500, 800, 1100], { hazardHeight: 2600 })
    expect(result.s).toBeCloseTo(1170, 9)
    expect(result.messages).toContainEqual({ code: 'annexCMatch', level: 'info', params: { table: 1, beams: 4 } })
    expect(matchBeamRow([300, 700, 1100])?.table).toBe(2)
  })

  it('takes the reach over the top beam from Table 2 when it is larger than the arm (8.1, 8.3.5)', () => {
    const result = beams([200, 600, 1000], { hazardHeight: 1200 })
    expect(step(result, 'reachOver')).toBe(1200)
    expect(step(result, 'reachCombined')).toBe(1200)
    expect(result.s).toBeCloseTo(1520, 9)
    expect(beams([200, 600, 1000], { hazardHeight: null }).s).toBeNull()
  })

  it('accepts a lowest beam up to 300 mm only in industrial use', () => {
    const industrial = beams([300, 600, 900, 1200])
    expect(industrial.s).not.toBeNull()
    expect(codes(industrial)).toContain('lowestBeamRiskAssessment')
    const publicArea = beams([300, 600, 900, 1200], { industrial: false })
    expect(publicArea.s).toBeNull()
    expect(codes(publicArea)).toContain('lowestBeamTooHigh')
  })

  it('needs a top beam at 900 mm unless the low two-beam row fits the opening', () => {
    const open = beams([200, 400])
    expect(open.s).toBeNull()
    expect(codes(open)).toEqual(expect.arrayContaining(['highestBeamTooLow', 'lowOpeningOnly']))
    const limited = beams([200, 400], { openingHeight: 600 })
    expect(limited.s).not.toBeNull()
    expect(codes(limited)).toContain('lowOpeningAllowed')
  })

  it('checks the beam spacing, which may only exceed 400 mm in front of a step', () => {
    const wide = beams([200, 700, 1100])
    expect(wide.s).toBeNull()
    expect(codes(wide)).toContain('beamSpacingTooLarge')
    expect(beams([200, 800, 1100]).s).toBeNull()
    expect(codes(beams([200, 900, 1000]))).toContain('beamSpacingTooLarge')
  })

  it('allows two beams up to 500 mm apart in front of a step higher than 300 mm (8.3.5)', () => {
    const atStep = { stepArrangement: true, stepHeight: 400, hazardHeight: 1400 }
    const ok = beams([550, 1000], atStep)
    expect(ok.s).not.toBeNull()
    expect(codes(ok)).toContain('stepArrangement')
    expect(codes(ok)).not.toContain('annexCNoMatch')
    expect(codes(beams([550, 1100], atStep))).toContain('stepSpacingTooLarge')
    expect(codes(beams([650, 1000], atStep))).toContain('stepLowestBeam')
    expect(codes(beams([550, 1000], { ...atStep, stepHeight: 300 }))).toContain('stepTooLow')
    expect(codes(beams([500, 700, 1000], atStep))).toContain('stepTwoBeams')
    expect(codes(beams([450, 850], atStep))).toContain('highestBeamTooLow')
    expect(beams([550, 1000], { ...atStep, stepHeight: null }).s).toBeNull()
  })

  it('warns when the heights match no row of Annex C', () => {
    expect(beams([150, 500, 850, 1200]).messages).toContainEqual({ code: 'annexCNoMatch', level: 'warning' })
  })

  it('needs at least two beams', () => {
    expect(codes(beams([200]))).toContain('tooFewBeams')
    expect(beams([]).s).toBeNull()
  })
})

describe('missing inputs', () => {
  it('asks once for the fields when everything is empty, without NaN anywhere', () => {
    const result = calculateSafetyDistance(emptySafetyDistanceInputs())
    expect(result.s).toBeNull()
    expect(result.k).toBeNull()
    expect(result.messages).toEqual([{ code: 'missingInputs', level: 'warning' }])
    expect(JSON.stringify(result)).not.toContain('NaN')
  })

  it('asks for T alone when it is the only gap, and for the fields when T is given', () => {
    const onlyT = sampleSafetyDistanceInputs()
    onlyT.responseTime.direct = null
    expect(calculateSafetyDistance(onlyT).messages).toEqual([{ code: 'missingResponseTime', level: 'warning' }])

    const onlyFields = emptySafetyDistanceInputs()
    onlyFields.responseTime.direct = 0.1
    expect(calculateSafetyDistance(onlyFields).messages).toEqual([{ code: 'missingInputs', level: 'warning' }])
  })
})
