import {
  inRange,
  isFieldRelevant,
  MAX_SEGMENTS,
  NUMERIC_FIELDS,
  SEGMENT_LIMITS,
} from './model'
import type { DriveSizingInput, NumericKey, Orientation, SegmentInput, Transmission } from './model'

/**
 * Sizing of a servo drive on a linear axis over a motion profile.
 *
 * Positions and forces are signed along the axis, positive forward or up.
 * Every move segment has a constant acceleration and keeps its direction, so
 * the drive force, the efficiency regime and therefore the motor torque are
 * constant within it; one value per segment describes the whole segment and
 * no segment ever needs to be split.
 *
 * The drive force is the sum of what the drive has to supply: the inertia
 * force m·a, the gravity component m·g·sin α (which always pulls down), the
 * guide friction µ·m·g·cos α and the process force, both against the
 * direction of travel. On a vertical axis cos α is zero, the weight does not
 * load the guides and there is no friction.
 *
 * When the drive force points along the travel the motor drives the load and
 * the losses of gearbox and transmission add to its torque; when it points
 * against the travel the load drives the motor (braking, lowering) and the
 * losses take some of the torque off. Rotating inertias are referred to the
 * motor shaft without losses.
 */

export const GRAVITY = 9.81
const KG_CM2_TO_KG_M2 = 1e-4
// Tolerance for comparing positions in mm and speeds in m/s, far below
// anything an input field can express.
const EPSILON = 1e-9

export type IssueCode =
  | 'required'
  | 'range'
  | 'noMove'
  | 'tooManySegments'
  | 'segmentRequired'
  | 'segmentRange'
  | 'segmentDistance'
  | 'segmentStill'
  | 'segmentDuration'
  | 'speedJump'
  | 'notClosed'
  | 'brakeMissing'

/** A field or segment the user has to fix, or a remark on a calculated profile. */
export interface Issue {
  code: IssueCode
  field?: NumericKey
  /** Zero-based index of the segment. */
  segment?: number
}

export type SegmentPhase = 'accelerating' | 'constant' | 'decelerating' | 'holdingBrake' | 'holdingMotor'

export interface SegmentResult {
  index: number
  kind: 'move' | 'pause'
  phase: SegmentPhase
  /** +1 forward or up, -1 backward or down, 0 at standstill. */
  direction: 1 | -1 | 0
  payload: boolean
  massKg: number
  startTimeS: number
  durationS: number
  startMm: number
  endMm: number
  /** Signed speeds along the axis in m/s. */
  startSpeed: number
  endSpeed: number
  accelerationMs2: number
  /** Force the drive applies to the load, signed along the axis. */
  forceN: number
  /** The load drives the motor in this segment. */
  regenerative: boolean
  /** Highest motor speed within the segment. */
  speedRpm: number
  /** Signed motor torque, positive in the forward or up sense. */
  torqueNm: number
  /** Signed torque at the gearbox output, the input shaft of the axis. */
  axisTorqueNm: number
  outOfStroke: boolean
}

export type CheckKey =
  | 'peakTorque'
  | 'rmsTorque'
  | 'maxSpeed'
  | 'ratedSpeed'
  | 'axisTorque'
  | 'stroke'
  | 'brakeHolding'

/** `pass` and `fail` compare against a hard limit; `warn` and `info` only point something out. */
export type CheckStatus = 'pass' | 'fail' | 'warn' | 'info'

export interface Check {
  key: CheckKey
  value: number
  limit: number | null
  /** value / limit, or null without a limit. */
  utilisation: number | null
  status: CheckStatus
  /** Zero-based index of the segment where the value occurs. */
  segment?: number
}

/** How the brake stops the fastest downward move with payload, ignoring its response time. */
export interface BrakeStop {
  speedMs: number
  massKg: number
  /** Null when gravity outweighs the brake and the load cannot be stopped. */
  decelerationMs2: number | null
  distanceMm: number | null
  timeS: number | null
}

export interface DriveSizingSuccess {
  ok: true
  radiusM: number
  /** Motor, gearbox and axis inertia referred to the motor shaft. */
  inertiaKgM2: number
  segments: SegmentResult[]
  cycleTimeS: number
  peakTorqueNm: number
  rmsTorqueNm: number
  maxSpeedRpm: number
  minPositionMm: number
  maxPositionMm: number
  endPositionMm: number
  checks: Check[]
  brakeStop: BrakeStop | null
  warnings: Issue[]
}

export interface DriveSizingFailure {
  ok: false
  errors: Issue[]
}

export type DriveSizingResult = DriveSizingSuccess | DriveSizingFailure

type OptionalKey = 'axisTorqueLimitNm' | 'maxSpeedRpm'

type Resolved = { [K in Exclude<NumericKey, OptionalKey>]: number } & {
  orientation: Orientation
  transmission: Transmission
  axisTorqueLimitNm: number | null
  maxSpeedRpm: number | null
}

interface ResolvedMove {
  kind: 'move'
  distanceMm: number
  startSpeed: number
  endSpeed: number
  payload: boolean
}

interface ResolvedPause {
  kind: 'pause'
  durationS: number
  payload: boolean
  brake: boolean
}

type ResolvedSegment = ResolvedMove | ResolvedPause

function validateSettings(input: DriveSizingInput, errors: Issue[]): Resolved {
  const values: Partial<Record<NumericKey, number | null>> = {}
  for (const field of NUMERIC_FIELDS) {
    const value = input[field.key]
    if (!isFieldRelevant(field.key, input)) {
      values[field.key] = 0
    } else if (value === null) {
      if (!field.optional) errors.push({ code: 'required', field: field.key })
      values[field.key] = field.optional ? (field.emptyValue ?? null) : 0
    } else {
      if (!inRange(field, value)) errors.push({ code: 'range', field: field.key })
      values[field.key] = value
    }
  }
  return { ...values, orientation: input.orientation, transmission: input.transmission } as Resolved
}

function validateSegments(segments: readonly SegmentInput[], errors: Issue[]): ResolvedSegment[] {
  if (segments.length > MAX_SEGMENTS) errors.push({ code: 'tooManySegments' })
  if (!segments.some((segment) => segment.kind === 'move')) errors.push({ code: 'noMove' })
  return segments.map((segment, index): ResolvedSegment => {
    if (segment.kind === 'pause') {
      const { durationS } = segment
      if (durationS === null) {
        errors.push({ code: 'segmentRequired', segment: index })
      } else if (!inRange(SEGMENT_LIMITS.durationS, durationS)) {
        errors.push({ code: 'segmentRange', segment: index })
      } else if (durationS <= 0) {
        errors.push({ code: 'segmentDuration', segment: index })
      }
      return { kind: 'pause', durationS: durationS ?? 0, payload: segment.payload, brake: segment.brake }
    }
    const { distanceMm, startSpeed, endSpeed } = segment
    if (distanceMm === null || startSpeed === null || endSpeed === null) {
      errors.push({ code: 'segmentRequired', segment: index })
    } else if (
      !inRange(SEGMENT_LIMITS.distanceMm, distanceMm) ||
      !inRange(SEGMENT_LIMITS.speed, startSpeed) ||
      !inRange(SEGMENT_LIMITS.speed, endSpeed)
    ) {
      errors.push({ code: 'segmentRange', segment: index })
    } else if (distanceMm === 0) {
      errors.push({ code: 'segmentDistance', segment: index })
    } else if (startSpeed === 0 && endSpeed === 0) {
      errors.push({ code: 'segmentStill', segment: index })
    }
    return {
      kind: 'move',
      distanceMm: distanceMm ?? 0,
      startSpeed: startSpeed ?? 0,
      endSpeed: endSpeed ?? 0,
      payload: segment.payload,
    }
  })
}

/** sin α and cos α, exact for the horizontal and vertical axis. */
export function axisAngle(orientation: Orientation, angleDeg: number): { sin: number; cos: number } {
  if (orientation === 'horizontal') return { sin: 0, cos: 1 }
  if (orientation === 'vertical') return { sin: 1, cos: 0 }
  const rad = (angleDeg * Math.PI) / 180
  return { sin: Math.sin(rad), cos: Math.cos(rad) }
}

/** Travel per radian of the axis input shaft, in m: D/2 for a pinion or pulley, p/2π for a screw. */
export function effectiveRadiusM(
  transmission: Transmission,
  diameterMm: number,
  pitchMm: number,
): number {
  return transmission === 'screw' ? pitchMm / (2 * Math.PI) / 1000 : diameterMm / 2 / 1000
}

/** Motor speed in rpm for an axis speed in m/s. */
export function motorSpeedRpm(speedMs: number, ratio: number, radiusM: number): number {
  return ((speedMs * ratio) / (2 * Math.PI * radiusM)) * 60
}

/**
 * Motor torque for a drive force. The efficiency divides when the motor
 * drives the load and multiplies when the load drives the motor.
 */
export function loadTorqueNm(
  forceN: number,
  radiusM: number,
  ratio: number,
  efficiency: number,
  regenerative: boolean,
): number {
  const ideal = (forceN * radiusM) / ratio
  return regenerative ? ideal * efficiency : ideal / efficiency
}

function signedSpeed(segment: ResolvedSegment, at: 'start' | 'end'): number {
  if (segment.kind === 'pause') return 0
  const direction = Math.sign(segment.distanceMm)
  return direction * (at === 'start' ? segment.startSpeed : segment.endSpeed)
}

function limitCheck(key: CheckKey, value: number, limit: number, segment?: number): Check {
  return {
    key,
    value,
    limit,
    utilisation: value / limit,
    status: value > limit * (1 + EPSILON) ? 'fail' : 'pass',
    ...(segment === undefined ? {} : { segment }),
  }
}

/** The segment with the largest absolute value of a quantity. */
function peakOf(
  segments: SegmentResult[],
  pick: (segment: SegmentResult) => number,
): { value: number; index: number } {
  let best = { value: 0, index: 0 }
  for (const segment of segments) {
    const value = Math.abs(pick(segment))
    if (value > best.value) best = { value, index: segment.index }
  }
  return best
}

export function sizeDrive(input: DriveSizingInput): DriveSizingResult {
  const errors: Issue[] = []
  const v = validateSettings(input, errors)
  const profile = validateSegments(input.segments, errors)
  if (errors.length > 0) return { ok: false, errors }

  const { sin, cos } = axisAngle(v.orientation, v.angleDeg)
  const radius = effectiveRadiusM(v.transmission, v.diameterMm, v.pitchMm)
  const efficiency = v.gearboxEfficiency * v.transmissionEfficiency
  const axisInertia = v.axisInertiaKgCm2 * KG_CM2_TO_KG_M2
  const inertia =
    (v.motorInertiaKgCm2 + v.gearboxInertiaKgCm2) * KG_CM2_TO_KG_M2 + axisInertia / (v.ratio * v.ratio)
  const brakeAvailable = v.brakeTorqueNm > 0
  const massOf = (payload: boolean) => v.carriageMassKg + (payload ? v.payloadMassKg : 0)

  const warnings: Issue[] = []
  const segments: SegmentResult[] = []
  let time = 0
  let position = 0

  profile.forEach((segment, index) => {
    const massKg = massOf(segment.payload)
    const startMm = position
    const base = { index, payload: segment.payload, massKg, startTimeS: time, startMm }

    if (segment.kind === 'pause') {
      // Static friction may carry part of the weight, but it is not relied
      // on; the holding torque is divided by the efficiency to stay safe.
      const forceN = massKg * GRAVITY * sin
      const braked = segment.brake && brakeAvailable
      if (segment.brake && !brakeAvailable) warnings.push({ code: 'brakeMissing', segment: index })
      segments.push({
        ...base,
        kind: 'pause',
        phase: braked ? 'holdingBrake' : 'holdingMotor',
        direction: 0,
        durationS: segment.durationS,
        endMm: position,
        startSpeed: 0,
        endSpeed: 0,
        accelerationMs2: 0,
        forceN,
        regenerative: false,
        speedRpm: 0,
        torqueNm: braked ? 0 : loadTorqueNm(forceN, radius, v.ratio, efficiency, false),
        axisTorqueNm: (forceN * radius) / v.transmissionEfficiency,
        outOfStroke: false,
      })
      time += segment.durationS
      return
    }

    const direction = segment.distanceMm > 0 ? 1 : -1
    const length = Math.abs(segment.distanceMm) / 1000
    const { startSpeed, endSpeed } = segment
    const accelerationMs2 = (direction * (endSpeed * endSpeed - startSpeed * startSpeed)) / (2 * length)
    const durationS = length / ((startSpeed + endSpeed) / 2)
    const resistance = v.friction * massKg * GRAVITY * cos + v.processForceN
    const forceN = massKg * accelerationMs2 + massKg * GRAVITY * sin + direction * resistance
    const regenerative = forceN * direction < 0
    const angularAcceleration = (accelerationMs2 * v.ratio) / radius
    const torqueNm =
      loadTorqueNm(forceN, radius, v.ratio, efficiency, regenerative) + inertia * angularAcceleration
    // The gearbox output turns the axis input shaft, so it carries the load
    // torque through the transmission plus the acceleration of the pinion,
    // pulley or screw itself.
    const transmissionTorque = forceN * radius
    const axisTorqueNm =
      (regenerative
        ? transmissionTorque * v.transmissionEfficiency
        : transmissionTorque / v.transmissionEfficiency) +
      (axisInertia * accelerationMs2) / radius
    position += segment.distanceMm
    const motion =
      endSpeed > startSpeed ? 'accelerating' : endSpeed < startSpeed ? 'decelerating' : 'constant'
    segments.push({
      ...base,
      kind: 'move',
      phase: motion,
      direction,
      durationS,
      endMm: position,
      startSpeed: direction * startSpeed,
      endSpeed: direction * endSpeed,
      accelerationMs2,
      forceN,
      regenerative,
      speedRpm: motorSpeedRpm(Math.max(startSpeed, endSpeed), v.ratio, radius),
      torqueNm,
      axisTorqueNm,
      outOfStroke:
        Math.min(startMm, position) < -EPSILON || Math.max(startMm, position) > v.strokeMm + EPSILON,
    })
    time += durationS
  })

  // The cycle repeats, so the first segment follows the last one.
  profile.forEach((segment, index) => {
    const previous = profile[(index - 1 + profile.length) % profile.length] as ResolvedSegment
    if (Math.abs(signedSpeed(previous, 'end') - signedSpeed(segment, 'start')) > EPSILON) {
      warnings.push({ code: 'speedJump', segment: index })
    }
  })
  if (Math.abs(position) > EPSILON) warnings.push({ code: 'notClosed' })
  warnings.sort((a, b) => (a.segment ?? -1) - (b.segment ?? -1))

  const cycleTimeS = time
  const squaredTorqueTime = segments.reduce(
    (sum, segment) => sum + segment.torqueNm * segment.torqueNm * segment.durationS,
    0,
  )
  const rmsTorqueNm = Math.sqrt(squaredTorqueTime / cycleTimeS)
  const peakTorque = peakOf(segments, (segment) => segment.torqueNm)
  const peakSpeed = peakOf(segments, (segment) => segment.speedRpm)
  const peakAxisTorque = peakOf(segments, (segment) => segment.axisTorqueNm)
  const positions = [0, ...segments.map((segment) => segment.endMm)]
  const minPositionMm = Math.min(...positions)
  const maxPositionMm = Math.max(...positions)

  const checks: Check[] = [
    limitCheck('peakTorque', peakTorque.value, v.maxTorqueNm, peakTorque.index),
    limitCheck('rmsTorque', rmsTorqueNm, v.ratedTorqueNm),
    limitCheck('maxSpeed', peakSpeed.value, v.maxSpeedRpm ?? v.ratedSpeedRpm, peakSpeed.index),
  ]
  // Without a separate maximum speed the rated speed is the limit already.
  if (v.maxSpeedRpm !== null) {
    checks.push({
      key: 'ratedSpeed',
      value: peakSpeed.value,
      limit: v.ratedSpeedRpm,
      utilisation: peakSpeed.value / v.ratedSpeedRpm,
      status: peakSpeed.value > v.ratedSpeedRpm * (1 + EPSILON) ? 'warn' : 'info',
      segment: peakSpeed.index,
    })
  }
  checks.push(
    v.axisTorqueLimitNm === null
      ? {
          key: 'axisTorque',
          value: peakAxisTorque.value,
          limit: null,
          utilisation: null,
          status: 'info',
          segment: peakAxisTorque.index,
        }
      : limitCheck('axisTorque', peakAxisTorque.value, v.axisTorqueLimitNm, peakAxisTorque.index),
  )
  const strokeCheck = limitCheck('stroke', maxPositionMm, v.strokeMm)
  if (minPositionMm < -EPSILON) strokeCheck.status = 'fail'
  checks.push(strokeCheck)

  let brakeStop: BrakeStop | null = null
  if (sin > 0) {
    const fullMass = massOf(true)
    const holdingTorque = loadTorqueNm(fullMass * GRAVITY * sin, radius, v.ratio, efficiency, false)
    const required = holdingTorque * v.brakeSafetyFactor
    checks.push(
      brakeAvailable
        ? limitCheck('brakeHolding', required, v.brakeTorqueNm)
        : { key: 'brakeHolding', value: required, limit: null, utilisation: null, status: 'warn' },
    )
    const downSpeeds = segments
      .filter((segment) => segment.direction < 0)
      .map((segment) => Math.max(Math.abs(segment.startSpeed), Math.abs(segment.endSpeed)))
    if (brakeAvailable && downSpeeds.length > 0) {
      const axis = { ...v, sin, radius, efficiency, inertia }
      brakeStop = brakeStopping(Math.max(...downSpeeds), fullMass, axis)
    }
  }

  return {
    ok: true,
    radiusM: radius,
    inertiaKgM2: inertia,
    segments,
    cycleTimeS,
    peakTorqueNm: peakTorque.value,
    rmsTorqueNm,
    maxSpeedRpm: peakSpeed.value,
    minPositionMm,
    maxPositionMm,
    endPositionMm: position,
    checks,
    brakeStop,
    warnings,
  }
}

/**
 * Stopping a downward move with the brake alone. The brake torque reaches the
 * load through the gearbox and transmission and is reduced by their
 * efficiency, guide friction and process force are left out, and the rotating
 * inertias are referred to the load as J·(i/r)². All three keep the result on
 * the safe side.
 */
interface BrakingAxis {
  brakeTorqueNm: number
  ratio: number
  sin: number
  radius: number
  efficiency: number
  inertia: number
}

function brakeStopping(speedMs: number, massKg: number, axis: BrakingAxis): BrakeStop {
  const brakeForce = (axis.brakeTorqueNm * axis.ratio * axis.efficiency) / axis.radius
  const reflectedMass = axis.inertia * (axis.ratio / axis.radius) ** 2
  const deceleration = (brakeForce - massKg * GRAVITY * axis.sin) / (massKg + reflectedMass)
  if (deceleration <= 0) return { speedMs, massKg, decelerationMs2: null, distanceMm: null, timeS: null }
  return {
    speedMs,
    massKg,
    decelerationMs2: deceleration,
    distanceMm: ((speedMs * speedMs) / (2 * deceleration)) * 1000,
    timeS: speedMs / deceleration,
  }
}

/** Points of the axis speed over the cycle, linear within each segment. */
export function speedTrace(segments: readonly SegmentResult[]): Array<[number, number]> {
  return segments.flatMap((segment): Array<[number, number]> => [
    [segment.startTimeS, segment.startSpeed],
    [segment.startTimeS + segment.durationS, segment.endSpeed],
  ])
}

/** Points of the motor torque over the cycle, constant within each segment. */
export function torqueTrace(segments: readonly SegmentResult[]): Array<[number, number]> {
  return segments.flatMap((segment): Array<[number, number]> => [
    [segment.startTimeS, segment.torqueNm],
    [segment.startTimeS + segment.durationS, segment.torqueNm],
  ])
}
