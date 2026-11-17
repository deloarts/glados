import { describe, expect, it } from 'vitest'

import { emptySafetyDistanceInputs, parseNumberList, roundUp } from '../inputs'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { decodeSafetyDistanceInputs, encodeSafetyDistanceInputs, SAFETY_DISTANCE_INPUT_KEYS } from '../inputRecord'
import type { SafetyDistanceInputs } from '../types'

function variant(change: (inputs: SafetyDistanceInputs) => void): SafetyDistanceInputs {
  const inputs = sampleSafetyDistanceInputs()
  change(inputs)
  return inputs
}

const VARIANTS: Record<string, SafetyDistanceInputs> = {
  curtain: variant((i) => {
    i.supplement = 25
    i.responseTime = { ...i.responseTime, method: 'components', tI: 0.015, tO: 0.004, tM: 0.2, tF: 0.01, tS: 0.008 }
    i.espe = {
      ...i.espe,
      detection: 30.5,
      topEdge: 1500,
      bottomEdge: 150,
      hazardHeight: 1100,
      industrial: false,
      restart: true,
      structureAbove: true,
      structureTop: 1800,
      structureBelow: true,
      structureGap: 100,
    }
  }),
  multiBeam: variant((i) => {
    i.responseTime = { ...i.responseTime, method: 'measured', cold: [0.561, 0.553], warm: [0.663], tF: 0.02 }
    i.espe = { ...i.espe, device: 'multiBeam', beamHeights: [200, 400], openingHeight: 550, industrial: false }
  }),
  multiBeamStep: variant((i) => {
    i.espe = { ...i.espe, device: 'multiBeam', beamHeights: [550, 1000], stepArrangement: true, stepHeight: 400 }
  }),
  singleBeam: variant((i) => {
    i.espe.device = 'singleBeam'
  }),
  parallel: variant((i) => {
    i.mode = 'parallel'
    i.supplement = 100
    i.parallel = { detection: 70, fieldHeight: 320, fieldDepth: null, obstacleGap: 40, standingDetected: true }
  }),
  twoHand: variant((i) => {
    i.mode = 'twoHand'
    i.twoHand.encroachmentPrevented = true
  }),
  twoHandOpen: variant((i) => {
    i.mode = 'twoHand'
    i.twoHand = { encroachmentPrevented: false, type: null, actuatorGap: null }
  }),
  holdToRun: variant((i) => {
    i.mode = 'holdToRun'
    i.holdToRun.actuation = 'foot'
  }),
  guardHinged: variant((i) => {
    i.mode = 'guard'
    i.guard = {
      ...i.guard,
      locking: true,
      unlockDelay: 0.3,
      reachThroughOwn: true,
      reachThrough: 850,
      openingMethod: 'hinged',
      guardWidth: 1000,
      angle: 5,
      guardThickness: 20,
    }
  }),
  guardDirect: variant((i) => {
    i.mode = 'guard'
    i.guard = { ...i.guard, openingShape: 'slot', slotLength: 60, opening: 25 }
  }),
  guardSquare: variant((i) => {
    i.mode = 'guard'
    i.guard = { ...i.guard, openingShape: 'square', opening: 12 }
  }),
  structure: variant((i) => {
    i.mode = 'structure'
    i.structure = { hazardHeight: 1500, structureHeight: 1700, distance: 850, lowRisk: true }
  }),
  openingSlot: variant((i) => {
    i.mode = 'opening'
    i.opening = { shape: 'slot', size: 25, slotLength: 60, limb: 'upper', children: true, distance: 300 }
  }),
  openingLower: variant((i) => {
    i.mode = 'opening'
    i.opening = { shape: 'round', size: 70, slotLength: null, limb: 'lower', children: false, distance: null }
  }),
  crushing: variant((i) => {
    i.mode = 'crushing'
    i.crushing = { bodyPart: 'hand', gap: 95 }
  }),
  crushingEmpty: variant((i) => {
    i.mode = 'crushing'
    i.crushing = { bodyPart: null, gap: null }
  }),
}

describe('safety distance input record', () => {
  it('writes only the keys of the selected mode', () => {
    expect(encodeSafetyDistanceInputs(sampleSafetyDistanceInputs())).toEqual({
      mode: 'espe',
      tmode: 'direct',
      t: '0.1',
      z: '0',
      dev: 'curtain',
      de: '14',
      hdt: '1800',
      hdb: '0',
      hh: '1000',
      ind: '1',
      rs: '0',
      above: '0',
      below: '0',
    })
    expect(encodeSafetyDistanceInputs(VARIANTS.twoHand as SafetyDistanceInputs)).toEqual({
      mode: 'twoHand',
      tmode: 'direct',
      t: '0.1',
      prevent: '1',
      type: 'IIIC',
      gap: '550',
    })
    // The modes without a response time write none.
    expect(encodeSafetyDistanceInputs(VARIANTS.crushing as SafetyDistanceInputs)).toEqual({
      mode: 'crushing',
      part: 'hand',
      a: '95',
    })
  })

  it('leaves the two-hand checks open for a record written before they existed', () => {
    const decoded = decodeSafetyDistanceInputs({ mode: 'twoHand', tmode: 'direct', t: '0.1', prevent: '0' })
    expect(decoded.invalid).toBe(false)
    expect(decoded.inputs.twoHand).toEqual({ encroachmentPrevented: false, type: null, actuatorGap: null })
  })

  for (const [name, inputs] of Object.entries(VARIANTS)) {
    it(`round trips the ${name} inputs`, () => {
      const encoded = encodeSafetyDistanceInputs(inputs)
      for (const key of Object.keys(encoded)) expect(SAFETY_DISTANCE_INPUT_KEYS).toContain(key)
      const decoded = decodeSafetyDistanceInputs(encoded)
      expect(decoded.invalid).toBe(false)
      expect(encodeSafetyDistanceInputs(decoded.inputs)).toEqual(encoded)
      // A field the encoder leaves out for this setup comes back as the
      // cleared form has it; every other field comes back as it was sent.
      const sent = inputs[inputs.mode] as unknown as Record<string, unknown>
      const cleared = emptySafetyDistanceInputs()[inputs.mode] as unknown as Record<string, unknown>
      for (const [key, value] of Object.entries(decoded.inputs[inputs.mode])) {
        expect([sent[key], cleared[key]]).toContainEqual(value)
      }
    })
  }

  it('round trips the cleared form of a new calculation without calling it invalid', () => {
    const encoded = encodeSafetyDistanceInputs(emptySafetyDistanceInputs())
    const decoded = decodeSafetyDistanceInputs(encoded)
    expect(decoded.invalid).toBe(false)
    expect(encodeSafetyDistanceInputs(decoded.inputs)).toEqual(encoded)
    expect(decoded.inputs.espe).toMatchObject({ detection: null, topEdge: null, bottomEdge: null, hazardHeight: null })
    expect(decoded.inputs.responseTime.direct).toBeNull()
    expect(decoded.inputs.supplement).toBeNull()
  })

  it('keeps an empty field empty without calling the record invalid', () => {
    const decoded = decodeSafetyDistanceInputs({ mode: 'espe', t: '', hdt: '' })
    expect(decoded.invalid).toBe(false)
    expect(decoded.inputs.responseTime.direct).toBeNull()
    expect(decoded.inputs.espe.topEdge).toBeNull()
  })

  it('leaves garbage as the cleared form has it and says so', () => {
    const defaults = emptySafetyDistanceInputs()
    const garbage = [
      { mode: 'laser' },
      { t: 'abc' },
      { t: '-1' },
      { de: '0' },
      { de: '0x10' },
      { ind: 'yes' },
      { dev: 'mat' },
      { beams: '200,,800' },
      { tmode: 'measured', cold: '0.5,fast' },
      { mode: 'guard', w: '120' },
      { mode: 'guard', shape: 'hexagon' },
      { mode: 'opening', limb: 'arm' },
      { mode: 'crushing', part: 'tail' },
      { mode: 'twoHand', type: 'IV' },
    ]
    expect(garbage.filter((query) => !decodeSafetyDistanceInputs(query).invalid)).toEqual([])
    const decoded = decodeSafetyDistanceInputs({ mode: 'laser', t: 'abc', de: '500' })
    expect(decoded.inputs.mode).toBe(defaults.mode)
    expect(decoded.inputs.responseTime.direct).toBe(defaults.responseTime.direct)
    expect(decoded.inputs.espe.detection).toBe(defaults.espe.detection)
  })

  it('ignores unknown keys and reads the first of repeated values', () => {
    const decoded = decodeSafetyDistanceInputs({ calc: '12', tab: 'x', t: ['0.25', '0.3'] })
    expect(decoded.invalid).toBe(false)
    expect(decoded.inputs.responseTime.direct).toBe(0.25)
  })
})

describe('number lists typed by the user', () => {
  it('separates by spaces, line breaks, semicolons and, in English, commas', () => {
    expect(parseNumberList('0.561, 0.553\n0.612;0.544', false)).toEqual({
      values: [0.561, 0.553, 0.612, 0.544],
      rejected: [],
    })
  })

  it('reads a decimal comma in German and names what it cannot read', () => {
    expect(parseNumberList('0,561 0,553;\n0,612 fast', true)).toEqual({
      values: [0.561, 0.553, 0.612],
      rejected: ['fast'],
    })
  })
})

describe('rounding up', () => {
  it('never rounds below the value and ignores floating point noise', () => {
    expect(roundUp(1206.4000000000001, 1)).toBe(1206.4)
    expect(roundUp(1206.41, 1)).toBe(1206.5)
    expect(roundUp(200, 1)).toBe(200)
  })
})
