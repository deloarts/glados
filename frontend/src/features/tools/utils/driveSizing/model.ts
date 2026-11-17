/**
 * Inputs of the linear axis drive sizing and the cleared form they start from.
 *
 * Every number is nullable because it comes straight from an input field or a
 * saved calculation; the engine reports a missing or out-of-range value
 * instead of calculating with it. The field table below is the one place that
 * knows a field's range, unit and key in the saved inputs, so the input
 * fields, the decoder and the engine's validation can never disagree.
 */

/** Positive travel is forward on a horizontal axis and up on any other. */
export type Orientation = 'horizontal' | 'vertical' | 'inclined'

/** Rack and pinion and belt are sized by an effective diameter, a ball screw by its pitch. */
export type Transmission = 'rack' | 'belt' | 'screw'

export const ORIENTATIONS: readonly Orientation[] = ['horizontal', 'vertical', 'inclined']
export const TRANSMISSIONS: readonly Transmission[] = ['rack', 'belt', 'screw']

/** One stretch of constant acceleration; the distance is signed, the speeds are magnitudes. */
export interface MoveSegmentInput {
  kind: 'move'
  distanceMm: number | null
  startSpeed: number | null
  endSpeed: number | null
  payload: boolean
}

/** A standstill, held either by the brake or by the motor. */
export interface PauseSegmentInput {
  kind: 'pause'
  durationS: number | null
  payload: boolean
  brake: boolean
}

export type SegmentInput = MoveSegmentInput | PauseSegmentInput

/** A segment as the editor lists it, with a stable key for reordering. */
export type SegmentRow = SegmentInput & { id: number }

export interface NumericInputs {
  angleDeg: number | null
  strokeMm: number | null
  diameterMm: number | null
  pitchMm: number | null
  transmissionEfficiency: number | null
  axisTorqueLimitNm: number | null
  axisInertiaKgCm2: number | null
  ratio: number | null
  gearboxEfficiency: number | null
  gearboxInertiaKgCm2: number | null
  ratedSpeedRpm: number | null
  maxSpeedRpm: number | null
  ratedTorqueNm: number | null
  maxTorqueNm: number | null
  motorInertiaKgCm2: number | null
  brakeTorqueNm: number | null
  brakeSafetyFactor: number | null
  carriageMassKg: number | null
  payloadMassKg: number | null
  friction: number | null
  processForceN: number | null
}

export type NumericKey = keyof NumericInputs

/** Everything except the motion profile. */
export interface DriveSizingSettings extends NumericInputs {
  orientation: Orientation
  transmission: Transmission
}

export interface DriveSizingInput extends DriveSizingSettings {
  segments: readonly SegmentInput[]
}

export type FieldGroup = 'axis' | 'gearbox' | 'motor' | 'load'

export interface NumericField {
  key: NumericKey
  /** Short key of the field in the saved inputs record. */
  param: string
  group: FieldGroup
  min: number
  max: number
  /** The lower bound itself is not allowed, as for an efficiency or a ratio. */
  exclusiveMin?: boolean
  /** Empty means "not given" and is valid, not missing. */
  optional?: boolean
  /** What an empty optional field counts as; without it, empty means "no limit". */
  emptyValue?: number
  /** Fraction digits the input field accepts. */
  digits: number
  unit: string
  /** Formula symbol as base letter and subscript, shown next to the label. */
  symbol: readonly [string, string]
}

export const NUMERIC_FIELDS: readonly NumericField[] = [
  { key: 'angleDeg', param: 'a', group: 'axis', min: 0, max: 90, digits: 2, unit: '°', symbol: ['α', ''] },
  { key: 'strokeMm', param: 'st', group: 'axis', min: 0, max: 100000, exclusiveMin: true, digits: 1, unit: 'mm', symbol: ['', ''] },
  { key: 'diameterMm', param: 'd', group: 'axis', min: 0, max: 5000, exclusiveMin: true, digits: 3, unit: 'mm', symbol: ['D', ''] },
  { key: 'pitchMm', param: 'p', group: 'axis', min: 0, max: 500, exclusiveMin: true, digits: 3, unit: 'mm', symbol: ['p', ''] },
  { key: 'transmissionEfficiency', param: 'et', group: 'axis', min: 0, max: 1, exclusiveMin: true, digits: 3, unit: '', symbol: ['η', 't'] },
  { key: 'axisTorqueLimitNm', param: 'tq', group: 'axis', min: 0, max: 1000000, exclusiveMin: true, optional: true, digits: 2, unit: 'Nm', symbol: ['M', 'axis'] },
  { key: 'axisInertiaKgCm2', param: 'jp', group: 'axis', min: 0, max: 1000000, digits: 3, optional: true, emptyValue: 0, unit: 'kg·cm²', symbol: ['J', 'p'] },
  { key: 'ratio', param: 'i', group: 'gearbox', min: 0, max: 10000, exclusiveMin: true, digits: 3, unit: '', symbol: ['i', ''] },
  { key: 'gearboxEfficiency', param: 'eg', group: 'gearbox', min: 0, max: 1, exclusiveMin: true, digits: 3, unit: '', symbol: ['η', 'g'] },
  { key: 'gearboxInertiaKgCm2', param: 'jg', group: 'gearbox', min: 0, max: 100000, digits: 3, optional: true, emptyValue: 0, unit: 'kg·cm²', symbol: ['J', 'g'] },
  { key: 'ratedSpeedRpm', param: 'nn', group: 'motor', min: 0, max: 100000, exclusiveMin: true, digits: 0, unit: 'rpm', symbol: ['n', 'N'] },
  { key: 'maxSpeedRpm', param: 'nx', group: 'motor', min: 0, max: 100000, exclusiveMin: true, optional: true, digits: 0, unit: 'rpm', symbol: ['n', 'max'] },
  { key: 'ratedTorqueNm', param: 'mn', group: 'motor', min: 0, max: 100000, exclusiveMin: true, digits: 3, unit: 'Nm', symbol: ['M', 'N'] },
  { key: 'maxTorqueNm', param: 'mx', group: 'motor', min: 0, max: 100000, exclusiveMin: true, digits: 3, unit: 'Nm', symbol: ['M', 'max'] },
  { key: 'motorInertiaKgCm2', param: 'jm', group: 'motor', min: 0, max: 1000000, digits: 3, unit: 'kg·cm²', symbol: ['J', 'm'] },
  { key: 'brakeTorqueNm', param: 'mb', group: 'motor', min: 0, max: 100000, optional: true, emptyValue: 0, digits: 3, unit: 'Nm', symbol: ['M', 'B'] },
  { key: 'brakeSafetyFactor', param: 'sf', group: 'motor', min: 1, max: 10, digits: 2, unit: '', symbol: ['S', 'B'] },
  { key: 'carriageMassKg', param: 'm0', group: 'load', min: 0, max: 100000, digits: 2, unit: 'kg', symbol: ['m', '0'] },
  { key: 'payloadMassKg', param: 'mp', group: 'load', min: 0, max: 100000, digits: 2, unit: 'kg', symbol: ['m', 'p'] },
  { key: 'friction', param: 'mu', group: 'load', min: 0, max: 1, digits: 3, unit: '', symbol: ['µ', ''] },
  { key: 'processForceN', param: 'f', group: 'load', min: 0, max: 10000000, optional: true, emptyValue: 0, digits: 1, unit: 'N', symbol: ['F', 'add'] },
]

export function numericField(key: NumericKey): NumericField {
  const field = NUMERIC_FIELDS.find((candidate) => candidate.key === key)
  if (!field) throw new Error(`Unknown drive sizing field ${key}`)
  return field
}

export function inRange(
  field: Pick<NumericField, 'min' | 'max' | 'exclusiveMin'>,
  value: number,
): boolean {
  if (!Number.isFinite(value) || value > field.max) return false
  return field.exclusiveMin ? value > field.min : value >= field.min
}

/**
 * Whether a field takes part in the calculation. The angle only matters on an
 * inclined axis and only one of diameter and pitch applies, so the others are
 * hidden and not validated. They are still saved, so switching back after
 * reopening finds the value that was entered.
 */
export function isFieldRelevant(
  key: NumericKey,
  settings: Pick<DriveSizingSettings, 'orientation' | 'transmission'>,
): boolean {
  if (key === 'angleDeg') return settings.orientation === 'inclined'
  if (key === 'diameterMm') return settings.transmission !== 'screw'
  if (key === 'pitchMm') return settings.transmission === 'screw'
  return true
}

/** Ranges of the segment values; the engine also rejects a move that never leaves standstill. */
export const SEGMENT_LIMITS = {
  distanceMm: { min: -100000, max: 100000 },
  speed: { min: 0, max: 50 },
  durationS: { min: 0, max: 86400 },
} as const

export const MAX_SEGMENTS = 40

let lastSegmentId = 0

/** Gives each segment a key that survives reordering in the editor. */
export function toSegmentRow(segment: SegmentInput): SegmentRow {
  lastSegmentId += 1
  return { ...segment, id: lastSegmentId }
}

/** The holding torque a brake needs above the static load, a policy value rather than data of the axis. */
const DEFAULT_BRAKE_SAFETY_FACTOR = 2

/**
 * A cleared form, the one every new calculation starts from: every number
 * empty and no motion profile, on the first orientation and transmission.
 * The brake safety factor keeps its default, since it is a policy value
 * rather than data of the axis.
 */
export function emptyDriveSizingInput(): DriveSizingInput {
  const numbers = {} as NumericInputs
  for (const field of NUMERIC_FIELDS) numbers[field.key] = null
  return {
    ...numbers,
    orientation: ORIENTATIONS[0] ?? 'horizontal',
    transmission: TRANSMISSIONS[0] ?? 'rack',
    brakeSafetyFactor: DEFAULT_BRAKE_SAFETY_FACTOR,
    segments: [],
  }
}
