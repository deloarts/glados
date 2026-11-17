import { describe, it, expect } from 'vitest'

import { sizeDrive, speedTrace, torqueTrace } from '../engine'
import type { Check, CheckKey, DriveSizingResult, DriveSizingSuccess, SegmentResult } from '../engine'
import { emptyDriveSizingInput } from '../model'
import { SAMPLE_SEGMENTS, SAMPLE_SETTINGS } from '@/features/tools/__tests__/fixtures'
import type { DriveSizingInput, DriveSizingSettings, SegmentInput } from '../model'

// A plain reference axis: D = 100 mm (r = 0.05 m), i = 10, lossless, no
// inertia, 100 kg without friction, and motor limits far above anything the
// tests reach unless a test lowers them.
const BASE: DriveSizingSettings = {
  ...SAMPLE_SETTINGS,
  orientation: 'horizontal',
  angleDeg: 30,
  strokeMm: 2000,
  transmission: 'rack',
  diameterMm: 100,
  transmissionEfficiency: 1,
  axisTorqueLimitNm: null,
  axisInertiaKgCm2: 0,
  ratio: 10,
  gearboxEfficiency: 1,
  gearboxInertiaKgCm2: 0,
  ratedSpeedRpm: 3000,
  maxSpeedRpm: null,
  ratedTorqueNm: 100,
  maxTorqueNm: 300,
  motorInertiaKgCm2: 0,
  brakeTorqueNm: 0,
  brakeSafetyFactor: 2,
  carriageMassKg: 100,
  payloadMassKg: 0,
  friction: 0,
  processForceN: 0,
}

function move(distanceMm: number, startSpeed: number, endSpeed: number, payload = false): SegmentInput {
  return { kind: 'move', distanceMm, startSpeed, endSpeed, payload }
}

function pause(durationS: number, brake = false, payload = false): SegmentInput {
  return { kind: 'pause', durationS, payload, brake }
}

function input(settings: Partial<DriveSizingSettings>, segments: SegmentInput[]): DriveSizingInput {
  return { ...BASE, ...settings, segments }
}

function solve(settings: Partial<DriveSizingSettings>, segments: SegmentInput[]): DriveSizingSuccess {
  const result: DriveSizingResult = sizeDrive(input(settings, segments))
  if (!result.ok) throw new Error(`Expected results, got ${JSON.stringify(result.errors)}`)
  return result
}

function segment(result: DriveSizingSuccess, index: number): SegmentResult {
  const found = result.segments[index]
  if (!found) throw new Error(`No segment ${index}`)
  return found
}

function check(result: DriveSizingSuccess, key: CheckKey): Check | undefined {
  return result.checks.find((candidate) => candidate.key === key)
}

describe('sizeDrive move segments', () => {
  it('derives acceleration and time from distance and speeds', () => {
    const result = solve({}, [move(200, 0, 0.5), move(200, 0.5, 0), move(-250, 0, 0.3), move(-250, 0.3, 0)])

    // a = (0.5² - 0²) / (2 * 0.2 m) = 0.625 m/s², t = 0.2 m / 0.25 m/s = 0.8 s
    expect(segment(result, 0).accelerationMs2).toBeCloseTo(0.625, 9)
    expect(segment(result, 0).durationS).toBeCloseTo(0.8, 9)
    expect(segment(result, 0).phase).toBe('accelerating')
    // Braking forward is a negative acceleration along the axis.
    expect(segment(result, 1).accelerationMs2).toBeCloseTo(-0.625, 9)
    expect(segment(result, 1).phase).toBe('decelerating')
    // Down from rest: a = -(0.3² / (2 * 0.25 m)) = -0.18 m/s², t = 0.25 / 0.15 = 1.667 s
    expect(segment(result, 2).accelerationMs2).toBeCloseTo(-0.18, 9)
    expect(segment(result, 2).durationS).toBeCloseTo(0.25 / 0.15, 9)
    expect(segment(result, 2).direction).toBe(-1)
    expect(segment(result, 2).endSpeed).toBeCloseTo(-0.3, 9)
    expect(result.cycleTimeS).toBeCloseTo(0.8 + 0.8 + 2 * (0.25 / 0.15), 9)
  })

  it('applies friction against the travel on a horizontal axis', () => {
    const result = solve({ friction: 0.1 }, [move(500, 0.5, 0.5), move(-500, 0.5, 0.5)])

    // F = µ·m·g = 0.1 * 100 kg * 9.81 = 98.1 N, against the travel either way
    expect(segment(result, 0).forceN).toBeCloseTo(98.1, 9)
    expect(segment(result, 1).forceN).toBeCloseTo(-98.1, 9)
  })

  it('carries the weight without guide friction on a vertical axis', () => {
    const result = solve({ orientation: 'vertical', friction: 0.1 }, [move(500, 0.5, 0.5), move(-500, 0.5, 0.5)])

    // F = m·g = 981 N up in both directions; cos 90° = 0 leaves no friction
    expect(segment(result, 0).forceN).toBeCloseTo(981, 9)
    expect(segment(result, 1).forceN).toBeCloseTo(981, 9)
  })

  it('splits the weight into slope and guide load on an inclined axis', () => {
    const result = solve({ orientation: 'inclined', angleDeg: 30, friction: 0.1 }, [
      move(500, 0.5, 0.5),
      move(-500, 0.5, 0.5),
    ])

    // Up:   F = 981 N * (sin 30° + 0.1 * cos 30°) = 981 * (0.5 + 0.0866025) = 575.457 N
    // Down: F = 981 N * (sin 30° - 0.1 * cos 30°) = 981 * (0.5 - 0.0866025) = 405.543 N
    expect(segment(result, 0).forceN).toBeCloseTo(575.457, 3)
    expect(segment(result, 1).forceN).toBeCloseTo(405.543, 3)
  })

  it('adds the process force against the travel', () => {
    const result = solve({ processForceN: 50 }, [move(500, 0.5, 0.5), move(-500, 0.5, 0.5)])

    expect(segment(result, 0).forceN).toBeCloseTo(50, 9)
    expect(segment(result, 1).forceN).toBeCloseTo(-50, 9)
  })

  it('divides by the efficiency when driving and multiplies when the load drives the motor', () => {
    const result = solve({ orientation: 'vertical', gearboxEfficiency: 0.9, transmissionEfficiency: 0.8 }, [
      move(500, 0.5, 0.5),
      move(-500, 0.5, 0.5),
    ])

    // Ideal torque F·r/i = 981 N * 0.05 m / 10 = 4.905 Nm, η = 0.9 * 0.8 = 0.72
    // Up, driving:       4.905 / 0.72 = 6.8125 Nm
    // Down, regenerative: 4.905 * 0.72 = 3.5316 Nm
    expect(segment(result, 0).regenerative).toBe(false)
    expect(segment(result, 0).torqueNm).toBeCloseTo(6.8125, 9)
    expect(segment(result, 1).regenerative).toBe(true)
    expect(segment(result, 1).torqueNm).toBeCloseTo(3.5316, 9)
    // At the axis input only the transmission counts: 981 * 0.05 / 0.8 = 61.3125 Nm
    // driving, 981 * 0.05 * 0.8 = 39.24 Nm regenerating.
    expect(segment(result, 0).axisTorqueNm).toBeCloseTo(61.3125, 9)
    expect(segment(result, 1).axisTorqueNm).toBeCloseTo(39.24, 9)
  })

  it('treats braking a horizontal move as regenerative', () => {
    const result = solve({ gearboxEfficiency: 0.9, transmissionEfficiency: 0.8 }, [move(125, 0.5, 0)])

    // a = -0.25 / 0.25 = -1 m/s², F = -100 N against a forward travel
    // M = -100 * 0.05 / 10 * 0.72 = -0.36 Nm
    expect(segment(result, 0).forceN).toBeCloseTo(-100, 9)
    expect(segment(result, 0).regenerative).toBe(true)
    expect(segment(result, 0).torqueNm).toBeCloseTo(-0.36, 9)
  })

  it('refers rotating inertias in kg·cm² to the motor shaft', () => {
    const result = solve(
      { carriageMassKg: 0, motorInertiaKgCm2: 10, gearboxInertiaKgCm2: 2, axisInertiaKgCm2: 100 },
      [move(500, 0, 1)],
    )

    // J = (10 + 2) kg·cm² * 1e-4 + 100 kg·cm² * 1e-4 / 10² = 1.2e-3 + 1e-4 = 1.3e-3 kg·m²
    // a = 1 / (2 * 0.5) = 1 m/s², motor α = a·i/r = 1 * 10 / 0.05 = 200 rad/s²
    // M = 1.3e-3 * 200 = 0.26 Nm; the axis shaft accelerates J_p alone: 0.01 * 1 / 0.05 = 0.2 Nm
    expect(result.inertiaKgM2).toBeCloseTo(1.3e-3, 12)
    expect(segment(result, 0).forceN).toBe(0)
    expect(segment(result, 0).torqueNm).toBeCloseTo(0.26, 9)
    expect(segment(result, 0).axisTorqueNm).toBeCloseTo(0.2, 9)
  })

  it('uses the pitch of a ball screw as 2π times the radius', () => {
    const result = solve({ transmission: 'screw', pitchMm: 10, ratio: 1 }, [move(500, 0.5, 0.5)])

    // r = 10 mm / 2π = 1.5915 mm; 0.5 m/s at 10 mm per turn is 50 rev/s = 3000 rpm
    expect(result.radiusM).toBeCloseTo(0.01 / (2 * Math.PI), 12)
    expect(segment(result, 0).speedRpm).toBeCloseTo(3000, 9)
  })
})

describe('sizeDrive pauses and RMS', () => {
  it('holds the weight with the motor or the brake and averages over the whole cycle', () => {
    const result = solve({ orientation: 'vertical', brakeTorqueNm: 20 }, [
      move(500, 0.5, 0.5),
      pause(1),
      move(-500, 0.5, 0.5),
      pause(1, true),
    ])

    // Every segment but the braked pause needs 981 N * 0.05 m / 10 = 4.905 Nm
    // for 1 s; the braked pause needs 0 Nm. Cycle 4 s.
    // RMS = sqrt((3 * 4.905² * 1 s) / 4 s) = 4.905 * sqrt(0.75) = 4.247855 Nm
    expect(segment(result, 1).phase).toBe('holdingMotor')
    expect(segment(result, 1).torqueNm).toBeCloseTo(4.905, 9)
    expect(segment(result, 3).phase).toBe('holdingBrake')
    expect(segment(result, 3).torqueNm).toBe(0)
    expect(result.cycleTimeS).toBeCloseTo(4, 9)
    expect(result.rmsTorqueNm).toBeCloseTo(4.905 * Math.sqrt(0.75), 9)
    expect(check(result, 'rmsTorque')).toMatchObject({ limit: 100, status: 'pass' })
  })

  it('divides the holding torque by the efficiency to stay on the safe side', () => {
    const result = solve({ orientation: 'vertical', gearboxEfficiency: 0.9, transmissionEfficiency: 0.8 }, [
      move(500, 0.5, 0),
      pause(2),
    ])

    // 4.905 Nm / 0.72 = 6.8125 Nm, although the load would back-drive with 4.905 * 0.72
    expect(segment(result, 1).torqueNm).toBeCloseTo(6.8125, 9)
  })

  it('lets the motor hold when a pause asks for a brake the motor does not have', () => {
    const result = solve({ orientation: 'vertical', brakeTorqueNm: 0 }, [move(500, 0.5, 0), pause(1, true)])

    expect(segment(result, 1).phase).toBe('holdingMotor')
    expect(segment(result, 1).torqueNm).toBeCloseTo(4.905, 9)
    expect(result.warnings).toContainEqual({ code: 'brakeMissing', segment: 1 })
  })
})

describe('sizeDrive checks', () => {
  it('compares the peak motor speed with the maximum, or the rated speed without one', () => {
    // n = v·i / (2π·r) * 60 = 0.5 * 10 / (2π * 0.05) * 60 = 954.93 rpm
    const segments = [move(500, 0.5, 0.5), move(-500, 0.5, 0.5)]
    const rpm = ((0.5 * 10) / (2 * Math.PI * 0.05)) * 60

    const ratedOnly = solve({ ratedSpeedRpm: 900 }, segments)
    expect(check(ratedOnly, 'maxSpeed')?.value).toBeCloseTo(rpm, 9)
    expect(check(ratedOnly, 'maxSpeed')).toMatchObject({ limit: 900, status: 'fail' })
    expect(check(ratedOnly, 'ratedSpeed')).toBeUndefined()

    const withMax = solve({ ratedSpeedRpm: 900, maxSpeedRpm: 1000 }, segments)
    expect(check(withMax, 'maxSpeed')).toMatchObject({ limit: 1000, status: 'pass' })
    expect(check(withMax, 'maxSpeed')?.utilisation).toBeCloseTo(rpm / 1000, 9)
    expect(check(withMax, 'ratedSpeed')).toMatchObject({ limit: 900, status: 'warn' })
  })

  it('finds the peak torque and checks it against M_max and the axis limit', () => {
    const result = solve({ orientation: 'vertical', maxTorqueNm: 5, axisTorqueLimitNm: 60 }, [
      move(250, 0, 0.5),
      move(250, 0.5, 0),
      move(-500, 0.5, 0.5),
    ])

    // Accelerating up: a = 0.25 / 0.5 = 0.5 m/s², F = 100 * (9.81 + 0.5) = 1031 N,
    // M = 1031 * 0.05 / 10 = 5.155 Nm > 5 Nm; axis 1031 * 0.05 = 51.55 Nm < 60 Nm
    expect(check(result, 'peakTorque')).toMatchObject({ limit: 5, status: 'fail', segment: 0 })
    expect(check(result, 'peakTorque')?.value).toBeCloseTo(5.155, 9)
    expect(check(result, 'axisTorque')).toMatchObject({ limit: 60, status: 'pass', segment: 0 })
    expect(check(result, 'axisTorque')?.value).toBeCloseTo(51.55, 9)
  })

  it('reports the axis torque as information without a limit', () => {
    const result = solve({}, [move(500, 0.5, 0.5)])

    expect(check(result, 'axisTorque')).toMatchObject({ limit: null, utilisation: null, status: 'info' })
  })

  it('fails the stroke check when the profile leaves the stroke at either end', () => {
    const beyond = solve({ strokeMm: 1000 }, [move(600, 0, 0.5), move(600, 0.5, 0), move(-1200, 0.5, 0.5)])
    expect(check(beyond, 'stroke')).toMatchObject({ value: 1200, limit: 1000, status: 'fail' })
    expect(segment(beyond, 0).outOfStroke).toBe(false)
    expect(segment(beyond, 1).outOfStroke).toBe(true)

    const below = solve({ strokeMm: 1000 }, [move(-100, 0.5, 0.5), move(100, 0.5, 0.5)])
    expect(below.minPositionMm).toBe(-100)
    expect(check(below, 'stroke')).toMatchObject({ value: 0, status: 'fail' })
    expect(segment(below, 0).outOfStroke).toBe(true)
  })

  it('checks the brake against the loaded holding torque times the safety factor', () => {
    const segments = [move(500, 0.5, 0.5), move(-500, 0.5, 0.5)]
    const loaded = { orientation: 'vertical' as const, carriageMassKg: 80, payloadMassKg: 20 }

    // (80 + 20) kg * 9.81 * 0.05 m / 10 = 4.905 Nm, times 2 = 9.81 Nm
    const strong = solve({ ...loaded, brakeTorqueNm: 10 }, segments)
    expect(check(strong, 'brakeHolding')?.value).toBeCloseTo(9.81, 9)
    expect(check(strong, 'brakeHolding')).toMatchObject({ limit: 10, status: 'pass' })
    expect(check(strong, 'brakeHolding')?.utilisation).toBeCloseTo(0.981, 9)

    expect(check(solve({ ...loaded, brakeTorqueNm: 9 }, segments), 'brakeHolding')?.status).toBe('fail')
    expect(check(solve({ ...loaded, brakeTorqueNm: 0 }, segments), 'brakeHolding')).toMatchObject({
      limit: null,
      status: 'warn',
    })
    // Without a gravity component there is nothing for a brake to hold.
    expect(check(solve({ brakeTorqueNm: 10 }, segments), 'brakeHolding')).toBeUndefined()
  })

  it('estimates how the brake stops the fastest downward move with payload', () => {
    const segments = [move(500, 0.3, 0.3), move(-250, 0.3, 0.5), move(-250, 0.5, 0.3)]
    const loaded = { orientation: 'vertical' as const, carriageMassKg: 80, payloadMassKg: 20 }

    // F_B = M_B·i·η / r = 10 * 10 * 1 / 0.05 = 2000 N against 981 N weight,
    // a = (2000 - 981) / 100 kg = 10.19 m/s², from 0.5 m/s:
    // s = 0.5² / (2 * 10.19) = 12.267 mm, t = 0.5 / 10.19 = 0.04907 s
    const stop = solve({ ...loaded, brakeTorqueNm: 10 }, segments).brakeStop
    expect(stop?.speedMs).toBeCloseTo(0.5, 9)
    expect(stop?.massKg).toBe(100)
    expect(stop?.decelerationMs2).toBeCloseTo(10.19, 9)
    expect(stop?.distanceMm).toBeCloseTo((0.25 / (2 * 10.19)) * 1000, 9)
    expect(stop?.timeS).toBeCloseTo(0.5 / 10.19, 9)

    // A rotor of 1 kg·cm² adds J·(i/r)² = 1e-4 * (10 / 0.05)² = 4 kg to stop:
    // a = 1019 / 104 = 9.798 m/s²
    const withRotor = solve({ ...loaded, brakeTorqueNm: 10, motorInertiaKgCm2: 1 }, segments).brakeStop
    expect(withRotor?.decelerationMs2).toBeCloseTo(1019 / 104, 9)

    // 4 Nm give 800 N, less than the weight: the load cannot be stopped.
    const weak = solve({ ...loaded, brakeTorqueNm: 4 }, segments).brakeStop
    expect(weak).toMatchObject({ decelerationMs2: null, distanceMm: null, timeS: null })
  })
})

describe('sizeDrive profile remarks and errors', () => {
  it('points out speed jumps, also across the end of the cycle, and an open cycle', () => {
    const result = solve({}, [move(500, 0, 0.5), pause(1), move(-200, 0.3, 0)])

    // Segment 1 starts at rest after a move ending at 0.5 m/s, segment 2 starts
    // at 0.3 m/s after a pause, and segment 0 is fine after the final standstill.
    expect(result.warnings).toEqual([{ code: 'notClosed' }, { code: 'speedJump', segment: 1 }, { code: 'speedJump', segment: 2 }])
    expect(result.endPositionMm).toBe(300)
  })

  it('accepts the default sample as a closed, continuous profile within all limits', () => {
    const result = solve({ ...SAMPLE_SETTINGS }, [...SAMPLE_SEGMENTS])

    expect(result.warnings).toEqual([])
    expect(result.checks.every((candidate) => candidate.status !== 'fail')).toBe(true)
    // Peak in segment 5, up with payload: F = 140 kg * (9.81 + 0.45) = 1436.4 N,
    // M = 1436.4 * 0.045835 / 12 / 0.855 + 4.5e-4 * 0.45 * 12 / 0.045835
    //   = 6.416899 + 0.053016 = 6.469915 Nm
    expect(check(result, 'peakTorque')?.value).toBeCloseTo(6.469915, 5)
    expect(check(result, 'peakTorque')?.segment).toBe(4)
    expect(result.maxPositionMm).toBe(1100)
    expect(result.cycleTimeS).toBeCloseTo(18.4667, 4)
  })

  it('rejects missing and out-of-range values and segments that never move', () => {
    const result = sizeDrive(
      input({ ratio: null, gearboxEfficiency: 1.2, axisTorqueLimitNm: null }, [
        move(0, 0, 0.5),
        move(100, 0, 0),
        pause(0),
        { kind: 'move', distanceMm: 100, startSpeed: null, endSpeed: 0.5, payload: false },
      ]),
    )

    expect(result).toEqual({
      ok: false,
      errors: [
        { code: 'required', field: 'ratio' },
        { code: 'range', field: 'gearboxEfficiency' },
        { code: 'segmentDistance', segment: 0 },
        { code: 'segmentStill', segment: 1 },
        { code: 'segmentDuration', segment: 2 },
        { code: 'segmentRequired', segment: 3 },
      ],
    })
  })

  it('ignores fields that do not apply to the axis', () => {
    const result = sizeDrive(input({ orientation: 'vertical', angleDeg: null, pitchMm: null }, [move(500, 0.5, 0.5)]))

    expect(result.ok).toBe(true)
  })

  it('lists only the required values for a cleared form', () => {
    const result = sizeDrive(emptyDriveSizingInput())

    // Inertias, process force and brake count as 0 when empty, the axis and
    // speed limits as not given, and the angle and pitch do not apply to a
    // horizontal rack; the safety factor keeps its default.
    const fields = [
      'strokeMm',
      'diameterMm',
      'transmissionEfficiency',
      'ratio',
      'gearboxEfficiency',
      'ratedSpeedRpm',
      'ratedTorqueNm',
      'maxTorqueNm',
      'motorInertiaKgCm2',
      'carriageMassKg',
      'payloadMassKg',
      'friction',
    ]
    expect(result).toEqual({
      ok: false,
      errors: [...fields.map((field) => ({ code: 'required', field })), { code: 'noMove' }],
    })
  })

  it('counts empty inertias, process force and brake as zero', () => {
    const segments = [move(500, 0, 1), move(-500, 1, 0)]
    const zeros = { axisInertiaKgCm2: 0, gearboxInertiaKgCm2: 0, processForceN: 0, brakeTorqueNm: 0 }
    const empty = { axisInertiaKgCm2: null, gearboxInertiaKgCm2: null, processForceN: null, brakeTorqueNm: null }

    expect(sizeDrive(input(empty, segments))).toEqual(sizeDrive(input(zeros, segments)))
  })

  it('needs at least one move', () => {
    const result = sizeDrive(input({}, [pause(1)]))

    expect(result).toEqual({ ok: false, errors: [{ code: 'noMove' }] })
  })
})

describe('chart traces', () => {
  it('draws speed linearly and torque as steps', () => {
    const result = solve({}, [move(200, 0, 0.5), pause(1)])

    expect(speedTrace(result.segments)).toEqual([
      [0, 0],
      [0.8, 0.5],
      [0.8, 0],
      [1.8, 0],
    ])
    // 100 kg * 0.625 m/s² * 0.05 m / 10 = 0.3125 Nm while accelerating
    const torque = torqueTrace(result.segments)
    expect(torque[0]?.[1]).toBeCloseTo(0.3125, 9)
    expect(torque[1]?.[0]).toBeCloseTo(0.8, 9)
    expect(torque[2]).toEqual([0.8, 0])
  })
})
