import {
  emptyDriveSizingInput,
  inRange,
  MAX_SEGMENTS,
  NUMERIC_FIELDS,
  SEGMENT_LIMITS,
} from './model'
import type {
  DriveSizingInput,
  DriveSizingSettings,
  NumericField,
  NumericKey,
  Orientation,
  SegmentInput,
  Transmission,
} from './model'

/**
 * The drive sizing as the flat string record a saved calculation stores.
 * Scalars use short keys, the motion profile goes into one `seg` entry:
 * segments separated by `|`, values by `:`, a move as
 * `m:distance:startSpeed:endSpeed:payload` and a pause as
 * `w:duration:payload:brake`, flags as 0 or 1. Every key is always written,
 * also for a field the current axis does not use, so a saved calculation
 * keeps its meaning even if a default changes and reopens exactly as it was
 * saved. An empty field is an empty value and reads back as an empty field,
 * so a cleared form reopens cleared.
 */

const ORIENTATION_CODES: Record<Orientation, string> = { horizontal: 'h', vertical: 'v', inclined: 'i' }
const TRANSMISSION_CODES: Record<Transmission, string> = { rack: 'r', belt: 'b', screw: 's' }

export const ORIENTATION_KEY = 'o'
export const TRANSMISSION_KEY = 'tr'
export const SEGMENTS_KEY = 'seg'

/** Every key the inputs record can hold. */
export const DRIVE_SIZING_INPUT_KEYS: readonly string[] = [
  ORIENTATION_KEY,
  TRANSMISSION_KEY,
  ...NUMERIC_FIELDS.map((field) => field.param),
  SEGMENTS_KEY,
]

// Six decimals are well below the input precision and keep float noise such
// as 0.30000000000000004 out of the record.
function formatNumber(value: number | null): string {
  return value === null ? '' : String(Math.round(value * 1e6) / 1e6)
}

const flag = (value: boolean) => (value ? '1' : '0')

function encodeSegment(segment: SegmentInput): string {
  if (segment.kind === 'pause') {
    return ['w', formatNumber(segment.durationS), flag(segment.payload), flag(segment.brake)].join(':')
  }
  return [
    'm',
    formatNumber(segment.distanceMm),
    formatNumber(segment.startSpeed),
    formatNumber(segment.endSpeed),
    flag(segment.payload),
  ].join(':')
}

export function encodeDriveSizingInputs(input: DriveSizingInput): Record<string, string> {
  const record: Record<string, string> = {
    [ORIENTATION_KEY]: ORIENTATION_CODES[input.orientation],
    [TRANSMISSION_KEY]: TRANSMISSION_CODES[input.transmission],
  }
  for (const field of NUMERIC_FIELDS) record[field.param] = formatNumber(input[field.key])
  record[SEGMENTS_KEY] = input.segments.map(encodeSegment).join('|')
  return record
}

const NUMBER_PATTERN = /^-?(\d+(\.\d*)?|\.\d+)$/

function parseNumber(raw: string): number | null {
  return NUMBER_PATTERN.test(raw) ? Number(raw) : null
}

function parseFlag(raw: string | undefined): boolean | null {
  return raw === '1' ? true : raw === '0' ? false : null
}

/**
 * A stored value: null for an empty field, undefined when the value is
 * unusable (not a plain number, or outside the field's range).
 */
function parseValue(
  raw: string | undefined,
  limits: Pick<NumericField, 'min' | 'max' | 'exclusiveMin'>,
): number | null | undefined {
  if (raw === undefined) return undefined
  if (raw === '') return null
  const value = parseNumber(raw)
  return value !== null && inRange(limits, value) ? value : undefined
}

function decodeSegment(raw: string): SegmentInput | null {
  const [kind, ...parts] = raw.split(':')
  if (kind === 'w' && parts.length === 3) {
    const durationS = parseValue(parts[0], SEGMENT_LIMITS.durationS)
    const payload = parseFlag(parts[1])
    const brake = parseFlag(parts[2])
    if (durationS === undefined || payload === null || brake === null) return null
    return { kind: 'pause', durationS, payload, brake }
  }
  if (kind === 'm' && parts.length === 4) {
    const distanceMm = parseValue(parts[0], SEGMENT_LIMITS.distanceMm)
    const startSpeed = parseValue(parts[1], SEGMENT_LIMITS.speed)
    const endSpeed = parseValue(parts[2], SEGMENT_LIMITS.speed)
    const payload = parseFlag(parts[3])
    if (distanceMm === undefined || startSpeed === undefined || endSpeed === undefined || payload === null) {
      return null
    }
    return { kind: 'move', distanceMm, startSpeed, endSpeed, payload }
  }
  return null
}

/** The profile of an inputs record, or null when any segment is unreadable; no segments is valid. */
export function decodeSegments(raw: string): SegmentInput[] | null {
  if (raw === '') return []
  const parts = raw.split('|')
  if (parts.length > MAX_SEGMENTS) return null
  const segments = parts.map(decodeSegment)
  return segments.every((segment) => segment !== null) ? (segments as SegmentInput[]) : null
}

function decodeCode<T extends string>(raw: string | null, codes: Record<T, string>): T | null {
  const entry = Object.entries(codes).find(([, code]) => code === raw)
  return entry ? (entry[0] as T) : null
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

export interface DecodedDriveSizing {
  input: DriveSizingInput
  /** A value was present but unusable and was left as the cleared form has it. */
  invalid: boolean
}

/**
 * Reads an inputs record back. A missing key leaves its field as the cleared
 * form has it and an empty value stays an empty field; an unusable value is
 * left the same way and marks the record invalid. The profile is dropped as
 * a whole, since a partly read profile would describe a different cycle.
 */
export function decodeDriveSizingInputs(record: Record<string, unknown>): DecodedDriveSizing {
  let invalid = false
  const { segments: emptySegments, ...emptySettings } = emptyDriveSizingInput()
  const settings: DriveSizingSettings = emptySettings

  const rawOrientation = stringOrNull(record[ORIENTATION_KEY])
  if (rawOrientation !== null) {
    const orientation = decodeCode(rawOrientation, ORIENTATION_CODES)
    if (orientation) settings.orientation = orientation
    else invalid = true
  }
  const rawTransmission = stringOrNull(record[TRANSMISSION_KEY])
  if (rawTransmission !== null) {
    const transmission = decodeCode(rawTransmission, TRANSMISSION_CODES)
    if (transmission) settings.transmission = transmission
    else invalid = true
  }

  for (const field of NUMERIC_FIELDS) {
    const raw = stringOrNull(record[field.param])
    if (raw === null) continue
    const value = parseValue(raw, field)
    if (value === undefined) invalid = true
    else settings[field.key as NumericKey] = value
  }

  let segments: SegmentInput[] = [...emptySegments]
  const rawSegments = stringOrNull(record[SEGMENTS_KEY])
  if (rawSegments !== null) {
    const decoded = decodeSegments(rawSegments)
    if (decoded) segments = decoded
    else invalid = true
  }

  return { input: { ...settings, segments }, invalid }
}
