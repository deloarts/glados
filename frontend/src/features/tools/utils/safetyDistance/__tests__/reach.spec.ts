import { describe, expect, it } from 'vitest'

import { calculateSafetyDistance } from '../calculate'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import {
  lookupOpening,
  lookupStructure,
  lowestStructureHeight,
  OPENINGS_CHILDREN,
  OPENINGS_LOWER,
  OPENINGS_UPPER,
} from '../iso13857'
import { calculateResponseTime } from '../responseTime'
import type { CrushingInputs, OpeningInputs, SafetyDistanceResult, StructureInputs } from '../types'

function run(change: (inputs: ReturnType<typeof sampleSafetyDistanceInputs>) => void): SafetyDistanceResult {
  const inputs = sampleSafetyDistanceInputs()
  change(inputs)
  return calculateSafetyDistance(inputs)
}

function structure(overrides: Partial<StructureInputs>): SafetyDistanceResult {
  return run((i) => {
    i.mode = 'structure'
    i.structure = { ...i.structure, ...overrides }
  })
}

function opening(overrides: Partial<OpeningInputs>): SafetyDistanceResult {
  return run((i) => {
    i.mode = 'opening'
    i.opening = { ...i.opening, ...overrides }
  })
}

function crushing(overrides: Partial<CrushingInputs>): SafetyDistanceResult {
  return run((i) => {
    i.mode = 'crushing'
    i.crushing = { ...i.crushing, ...overrides }
  })
}

function codes(result: SafetyDistanceResult): string[] {
  return result.messages.map((m) => m.code)
}

describe('ISO 13857, Tables 1 and 2: reaching over a structure', () => {
  it('reads grid values and the examples of Annex A', () => {
    expect(lookupStructure(1600, 1800, false)?.value).toBe(800)
    // Example 2: h_h 2300 mm and h_ps 1500 mm are read as 2200 and 1400.
    expect(lookupStructure(2300, 1500, false)?.value).toBe(1000)
    // Example 1: h_h 1500 mm and s_h 800 mm need a structure of 1800 mm.
    expect(lowestStructureHeight(1500, 800, false)).toBe(1800)
    expect(lookupStructure(1000, 900, false)).toBeNull()
  })

  it('reads the lower column and the larger row off the grid', () => {
    expect(lookupStructure(1000, 2699, false)?.value).toBe(0)
    expect(lookupStructure(2500, 1000, false)).toMatchObject({ value: 1100, rows: [2400, 2600] })
    expect(lookupStructure(100, 1200, false)?.value).toBe(900)
  })

  it('puts hazards from 2700 mm, or 2500 mm at low risk, out of reach', () => {
    expect(lookupStructure(2700, 1000, false)?.value).toBe(0)
    expect(lookupStructure(2650, 1000, false)?.value).toBe(900)
    expect(lookupStructure(2500, 1000, true)?.value).toBe(0)
    expect(lookupStructure(2000, 1000, true)?.value).toBe(1100)
  })

  it('reports low and uncovered structures, low risk and the check as built', () => {
    expect(codes(structure({ structureHeight: 1200 }))).toContain('structureLow')
    const tooLow = structure({ structureHeight: 900 })
    expect(tooLow.s).toBeNull()
    expect(codes(tooLow)).toContain('structureTooLow')
    const lowRisk = structure({ lowRisk: true })
    expect(lowRisk.ref).toMatchObject({ standard: 'iso13857', table: '1' })
    expect(lowRisk.messages).toContainEqual({ code: 'lowRiskTable', level: 'warning' })
    expect(codes(structure({ hazardHeight: 2800 }))).toContain('outOfReachAbove')

    const short = structure({ distance: 700 })
    expect(short.s).toBe(800)
    expect(short.messages).toContainEqual({ code: 'structureTooClose', level: 'error', params: { min: 800 } })
    expect(short.steps.find((s) => s.key === 'minStructureHeight')?.value).toBe(2000)
    expect(structure({ distance: 800 }).messages).toContainEqual({ code: 'distanceMet', level: 'info', params: { min: 800 } })
    expect(structure({ hazardHeight: null }).messages).toEqual([{ code: 'missingInputs', level: 'warning' }])
  })
})

describe('ISO 13857, Tables 4, 5 and 7: reaching through openings', () => {
  it('reads the rows with their upper limit included', () => {
    expect(lookupOpening(OPENINGS_UPPER, 'slot', 4)?.value).toBe(2)
    expect(lookupOpening(OPENINGS_UPPER, 'slot', 4.01)?.value).toBe(10)
    expect(lookupOpening(OPENINGS_UPPER, 'square', 40)?.value).toBe(200)
    expect(lookupOpening(OPENINGS_UPPER, 'round', 40)?.value).toBe(120)
    expect(lookupOpening(OPENINGS_UPPER, 'round', 120)?.value).toBe(850)
    expect(lookupOpening(OPENINGS_UPPER, 'round', 121)).toBeNull()
    expect(lookupOpening(OPENINGS_CHILDREN, 'square', 30)?.value).toBe(550)
    expect(lookupOpening(OPENINGS_CHILDREN, 'square', 101)).toBeNull()
    expect(lookupOpening(OPENINGS_LOWER, 'square', 15)?.value).toBe(0)
    expect(lookupOpening(OPENINGS_LOWER, 'slot', 200)?.value).toBeNull()
  })

  it('lowers the distance of a short slot only in the row its footnote names', () => {
    expect(lookupOpening(OPENINGS_UPPER, 'slot', 25, 65)).toMatchObject({ value: 200, reduced: true })
    expect(lookupOpening(OPENINGS_UPPER, 'slot', 25, 66)).toMatchObject({ value: 850, reduced: false })
    expect(lookupOpening(OPENINGS_UPPER, 'slot', 35, 40)).toMatchObject({ value: 850, reduced: false })
    expect(lookupOpening(OPENINGS_CHILDREN, 'slot', 15, 40)?.value).toBe(120)
    expect(lookupOpening(OPENINGS_LOWER, 'slot', 20, 75)?.value).toBe(50)
  })

  it('picks the table for the limbs and the age, and reports what it does not cover', () => {
    expect(opening({ shape: 'square', size: 25 }).s).toBe(120)
    expect(opening({ shape: 'square', size: 25, children: true }).s).toBe(550)
    const legs = opening({ shape: 'round', size: 70, limb: 'lower' })
    expect(legs.s).toBe(180)
    expect(legs.ref).toMatchObject({ standard: 'iso13857', clause: '4.3', table: '7' })
    expect(codes(legs)).toContain('lowerLimbsOnly')

    const beyond = opening({ shape: 'square', size: 150 })
    expect(beyond.s).toBeNull()
    expect(codes(beyond)).toContain('openingBeyondTable')
    expect(codes(opening({ shape: 'square', size: 250 }))).toContain('openingWholeBodyAccess')
    const slot = opening({ shape: 'slot', size: 200, limb: 'lower' })
    expect(slot.s).toBeNull()
    expect(codes(slot)).toContain('slotNotPermitted')
    expect(codes(opening({ shape: 'round', size: 250, limb: 'lower' }))).toContain('openingWholeBodyAccess')
  })

  it('checks the distance as built', () => {
    const short = opening({ shape: 'square', size: 40, distance: 150 })
    expect(short.s).toBe(200)
    expect(short.messages).toContainEqual({ code: 'openingTooClose', level: 'error', params: { min: 200 } })
  })
})

describe('ISO 13854: minimum gaps', () => {
  it('gives the gap of the body part and checks the gap as built', () => {
    expect(crushing({ bodyPart: 'body', gap: null }).s).toBe(500)
    expect(crushing({ bodyPart: 'finger', gap: null }).s).toBe(25)
    const short = crushing({ bodyPart: 'hand', gap: 90 })
    expect(short.s).toBe(100)
    expect(short.messages).toContainEqual({ code: 'gapTooSmall', level: 'error', params: { min: 100 } })
    expect(codes(crushing({ bodyPart: 'toes', gap: 60 }))).toEqual(
      expect.arrayContaining(['toesOverhang', 'gapLargeEnough']),
    )
    expect(crushing({ bodyPart: null }).messages).toEqual([{ code: 'missingInputs', level: 'warning' }])
  })

  it('ignores the response time and asks for nothing of it', () => {
    const result = run((i) => {
      i.mode = 'crushing'
      i.responseTime.direct = null
    })
    expect(result.t).toBeNull()
    expect(result.responseTime.steps).toEqual([])
    expect(codes(result)).not.toContain('missingResponseTime')
  })
})

describe('sampling interval of equation (7)', () => {
  it('adds t_S to the sum of components and cites equation (7)', () => {
    const inputs = sampleSafetyDistanceInputs().responseTime
    const base = { ...inputs, method: 'components' as const, tI: 0.02, tL: 0.01, tM: 0.17 }
    expect(calculateResponseTime(base).steps.at(-1)?.ref).toEqual({ clause: '5.4', equation: '3' })
    const sampled = calculateResponseTime({ ...base, tS: 0.008 })
    expect(sampled.t).toBeCloseTo(0.208, 12)
    expect(sampled.steps.at(-1)?.ref).toEqual({ clause: '6.1', equation: '7' })
  })
})
