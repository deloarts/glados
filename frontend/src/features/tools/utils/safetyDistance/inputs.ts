import type { SafetyDistanceInputs } from './types'

/**
 * A cleared form for a new calculation: a light curtain with a known response
 * time, every number empty and every switch off, apart from the industrial
 * environment, which most machines are built for. Openings start as slots,
 * the shape with the largest distances. Its encoded record decodes again
 * without being flagged invalid, since an empty value is an empty field.
 */
export function emptySafetyDistanceInputs(): SafetyDistanceInputs {
  return {
    mode: 'espe',
    responseTime: {
      method: 'direct',
      direct: null,
      tI: null,
      tL: null,
      tO: null,
      tD: null,
      tR: null,
      tM: null,
      tF: null,
      tS: null,
      cold: [],
      warm: [],
    },
    supplement: null,
    espe: {
      device: 'curtain',
      detection: null,
      topEdge: null,
      bottomEdge: null,
      hazardHeight: null,
      industrial: true,
      restart: false,
      structureAbove: false,
      structureTop: null,
      structureBelow: false,
      structureGap: null,
      beamHeights: [],
      openingHeight: null,
      stepArrangement: false,
      stepHeight: null,
    },
    parallel: {
      detection: null,
      fieldHeight: null,
      fieldDepth: null,
      obstacleGap: null,
      standingDetected: false,
    },
    twoHand: { encroachmentPrevented: false, type: null, actuatorGap: null },
    holdToRun: { actuation: 'hand' },
    guard: {
      locking: false,
      unlockDelay: null,
      reachThroughOwn: false,
      reachThrough: null,
      openingMethod: 'direct',
      openingShape: 'slot',
      slotLength: null,
      opening: null,
      guardWidth: null,
      angle: null,
      guardThickness: null,
    },
    structure: { hazardHeight: null, structureHeight: null, distance: null, lowRisk: false },
    opening: { shape: 'slot', size: null, slotLength: null, limb: 'upper', children: false, distance: null },
    crushing: { bodyPart: null, gap: null },
  }
}

export interface FieldLimit {
  min: number
  max: number
}

/**
 * Accepted ranges, shared by the input fields and the decoder of saved
 * records, so every value a field accepts also reads back unchanged.
 */
export const LIMITS = {
  time: { min: 0, max: 60 },
  length: { min: 0, max: 10000 },
  detection: { min: 1, max: 120 },
  parallelDetection: { min: 1, max: 1000 },
  angle: { min: 0, max: 90 },
} as const satisfies Record<string, FieldLimit>

/** Most samples or beam heights a list accepts. */
export const MAX_SAMPLES = 500
export const MAX_BEAMS = 20

/** A plain decimal number with a dot, or NaN; hex, words and empty text are rejected. */
export function parseDecimal(text: string): number {
  const trimmed = text.trim()
  return /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(trimmed) ? Number(trimmed) : Number.NaN
}

export function withinLimit(value: number, limit: FieldLimit): boolean {
  return Number.isFinite(value) && value >= limit.min && value <= limit.max
}

/**
 * Reads a list of numbers typed or pasted by the user. Values are separated
 * by spaces, line breaks or semicolons; a comma separates values too unless
 * `decimalComma` is set, in which case it is the decimal separator. Tokens
 * that are not numbers are returned separately so the field can name them.
 */
export function parseNumberList(text: string, decimalComma: boolean): { values: number[]; rejected: string[] } {
  const separators = decimalComma ? /[\s;]+/ : /[\s;,]+/
  const values: number[] = []
  const rejected: string[] = []
  for (const token of text.split(separators)) {
    if (token === '') continue
    const value = parseDecimal(decimalComma ? token.replace(',', '.') : token)
    if (Number.isFinite(value)) values.push(value)
    else rejected.push(token)
  }
  return { values, rejected }
}

/**
 * Rounds up to `digits` decimals, so a displayed separation distance is never
 * shorter than the calculated one. The value is first rounded to nine
 * decimals, so floating point noise such as 1206.4000000000001 does not
 * round up to the next step.
 */
export function roundUp(value: number, digits: number): number {
  const factor = 10 ** digits
  return Math.ceil(Number((value * factor).toFixed(9 - digits))) / factor
}
