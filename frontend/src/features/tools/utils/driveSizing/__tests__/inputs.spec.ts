import { describe, it, expect } from 'vitest'

import { emptyDriveSizingInput, MAX_SEGMENTS } from '../model'
import { SAMPLE_SEGMENTS, SAMPLE_SETTINGS } from '@/features/tools/__tests__/fixtures'
import type { DriveSizingInput } from '../model'
import {
  decodeDriveSizingInputs,
  decodeSegments,
  DRIVE_SIZING_INPUT_KEYS,
  encodeDriveSizingInputs,
} from '../inputs'

const SAMPLE_INPUT: DriveSizingInput = { ...SAMPLE_SETTINGS, segments: [...SAMPLE_SEGMENTS] }

describe('encodeDriveSizingInputs', () => {
  it('writes the sample with short keys and a compact profile', () => {
    const record = encodeDriveSizingInputs(SAMPLE_INPUT)

    expect(record).toMatchObject({ o: 'v', tr: 'r', st: '1200', d: '91.67', i: '12', mb: '13', mp: '40' })
    // Fields the axis does not use are kept, and limits not given are empty.
    expect(record).toMatchObject({ a: '30', p: '10', tq: '', nx: '' })
    expect(record.seg).toBe(
      'm:200:0:0.5:0|m:300:0.5:0.5:0|m:200:0.5:0:0|w:1:0:1|m:100:0:0.3:1|m:200:0.3:0.3:1|m:100:0.3:0:1|w:4:1:0|' +
        'm:-250:0:0.3:1|m:-400:0.3:0.3:1|m:-250:0.3:0:1|w:1:0:0|m:-50:0:0.5:0|m:-100:0.5:0.5:0|m:-50:0.5:0:0|w:3:0:0',
    )
    expect(Object.keys(record).sort()).toEqual([...DRIVE_SIZING_INPUT_KEYS].sort())
  })

  it('keeps float noise out of the record and writes an empty field as an empty value', () => {
    const record = encodeDriveSizingInputs({ ...SAMPLE_INPUT, friction: 0.1 + 0.2, ratio: null })

    expect(record.mu).toBe('0.3')
    expect(record.i).toBe('')
  })
})

describe('decodeDriveSizingInputs', () => {
  it('starts on the cleared form without saved inputs', () => {
    expect(decodeDriveSizingInputs({})).toEqual({ input: emptyDriveSizingInput(), invalid: false })
  })

  it('reads back what it writes', () => {
    const custom: DriveSizingInput = {
      ...SAMPLE_SETTINGS,
      orientation: 'inclined',
      angleDeg: 25,
      transmission: 'screw',
      pitchMm: 5,
      axisTorqueLimitNm: 50,
      maxSpeedRpm: 3000,
      processForceN: 120.5,
      segments: [
        { kind: 'move', distanceMm: 150, startSpeed: 0, endSpeed: 0.25, payload: true },
        { kind: 'move', distanceMm: -150, startSpeed: 0.25, endSpeed: 0, payload: false },
        { kind: 'pause', durationS: 0.5, payload: false, brake: true },
      ],
    }

    const decoded = decodeDriveSizingInputs(encodeDriveSizingInputs(custom))

    expect(decoded).toEqual({ input: custom, invalid: false })
  })

  it('leaves an unusable value as the cleared form has it and flags the record', () => {
    const decoded = decodeDriveSizingInputs({ o: 'x', st: 'abc', mu: '0.2', et: '0', i: '1e3', nn: ' 2000' })
    const empty = emptyDriveSizingInput()

    expect(decoded.invalid).toBe(true)
    expect(decoded.input.orientation).toBe(empty.orientation)
    expect(decoded.input.strokeMm).toBeNull()
    // An efficiency of 0 is outside the range, exponent and padded numbers are not read.
    expect(decoded.input.transmissionEfficiency).toBeNull()
    expect(decoded.input.ratio).toBeNull()
    expect(decoded.input.ratedSpeedRpm).toBeNull()
    // The usable value is kept.
    expect(decoded.input.friction).toBe(0.2)
  })

  it('reads an empty value back as an empty field', () => {
    expect(decodeDriveSizingInputs({ i: '' })).toMatchObject({ input: { ratio: null }, invalid: false })
  })

  it('reopens a cleared form exactly, without flagging it', () => {
    const empty = emptyDriveSizingInput()
    const record = encodeDriveSizingInputs(empty)

    // Every number empty, no segments, and the safety factor kept at 2.
    expect(record).toMatchObject({ o: 'h', tr: 'r', st: '', i: '', sf: '2', seg: '' })
    expect(decodeDriveSizingInputs(record)).toEqual({ input: empty, invalid: false })
  })

  it('drops a garbled profile as a whole', () => {
    const decoded = decodeDriveSizingInputs({ seg: 'm:200:0:0.5:0|garbage', mp: '10' })

    expect(decoded.invalid).toBe(true)
    expect(decoded.input.segments).toEqual([])
    expect(decoded.input.payloadMassKg).toBe(10)
  })
})

describe('decodeSegments', () => {
  it('reads moves and pauses', () => {
    expect(decodeSegments('m:-50.5:0.1:0:1|w:2:1:0')).toEqual([
      { kind: 'move', distanceMm: -50.5, startSpeed: 0.1, endSpeed: 0, payload: true },
      { kind: 'pause', durationS: 2, payload: true, brake: false },
    ])
  })

  it('reads an empty profile and empty values in a segment', () => {
    expect(decodeSegments('')).toEqual([])
    expect(decodeSegments('m::0:0.5:0|w::1:0')).toEqual([
      { kind: 'move', distanceMm: null, startSpeed: 0, endSpeed: 0.5, payload: false },
      { kind: 'pause', durationS: null, payload: true, brake: false },
    ])
  })

  it.each([
    ['m:100:0:0.5', 'a move without its payload flag'],
    ['m:100:0:0.5:2', 'a flag other than 0 or 1'],
    ['m:100:-1:0.5:0', 'a negative speed'],
    ['m:100:0:99:0', 'a speed above the limit'],
    ['w:-1:0:1', 'a negative pause'],
    ['w:1:0:1:0', 'a pause with an extra value'],
    ['m:100:0:0.5:', 'an empty flag'],
    ['x:1:0:1', 'an unknown kind'],
    [Array.from({ length: MAX_SEGMENTS + 1 }, () => 'w:1:0:0').join('|'), 'too many segments'],
  ])('rejects %j (%s)', (raw) => {
    expect(decodeSegments(raw)).toBeNull()
  })
})
