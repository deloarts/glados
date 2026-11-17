import type { CalcStep, SafetyMessage, StandardRef } from './types'

/** Approach speed of hand and arm (5.3.1). */
export const K_HAND = 2000
/** Approach speed of a walking person (5.3.1). */
export const K_WALK = 1600

/** Limit up to which the hand speed applies, and minimum once the walking speed is used. */
export const SWITCH_DISTANCE = 500
/** Minimum distance while the hand speed applies. */
export const MIN_DISTANCE_HAND = 100
/** Supplement where the public may be present (8.3.2, 8.3.3). */
export const PUBLIC_SUPPLEMENT = 75

export interface ApproachSpeedOptions {
  /** K = 1600 mm/s may replace 2000 mm/s once S exceeds 500 mm. */
  fallback: boolean
  /** The public may be present: no fallback and at least 75 mm more. */
  publicArea: boolean
}

export interface ApproachSpeedResult {
  k: number
  s: number
  sWithHand: number
  sWithWalk: number | null
  /** The minimum that raised S, if one did. */
  floor: number | null
  supplement: number
}

/**
 * The approach speed rule of 8.2.2, 8.3.2 and 8.3.3. S is first calculated
 * with K = 2000 mm/s and is at least 100 mm. Above 500 mm it may be
 * recalculated with K = 1600 mm/s and is then at least 500 mm. Where the
 * public may be present the recalculation is not allowed and 75 mm are
 * added; the supplement is added after the 100 mm minimum, which gives the
 * larger distance of the two possible orders.
 */
export function approachSpeedRule(
  t: number,
  reach: number,
  z: number,
  options: ApproachSpeedOptions,
): ApproachSpeedResult {
  const sWithHand = K_HAND * t + reach + z
  const fallback = options.fallback && !options.publicArea
  if (!fallback || sWithHand <= SWITCH_DISTANCE) {
    const floored = Math.max(sWithHand, MIN_DISTANCE_HAND)
    const supplement = options.publicArea ? PUBLIC_SUPPLEMENT : 0
    return {
      k: K_HAND,
      s: floored + supplement,
      sWithHand,
      sWithWalk: null,
      floor: sWithHand < MIN_DISTANCE_HAND ? MIN_DISTANCE_HAND : null,
      supplement,
    }
  }
  const sWithWalk = K_WALK * t + reach + z
  return {
    k: K_WALK,
    s: Math.max(sWithWalk, SWITCH_DISTANCE),
    sWithHand,
    sWithWalk,
    floor: sWithWalk < SWITCH_DISTANCE ? SWITCH_DISTANCE : null,
    supplement: 0,
  }
}

/**
 * The worked steps of the approach speed rule for a reach distance named
 * `reachSymbol`, plus the messages that explain which branch applied.
 */
export function approachSpeedSteps(
  rule: ApproachSpeedResult,
  t: number,
  reach: number,
  z: number,
  reachSymbol: string,
  ref: StandardRef,
): { steps: CalcStep[]; messages: SafetyMessage[] } {
  const steps: CalcStep[] = [
    {
      key: 'withHandSpeed',
      symbol: 'S',
      formula: `2000 · T + ${reachSymbol} + Z`,
      expression: '2000 · {t} + {reach} + {z}',
      args: { t, reach, z },
      value: rule.sWithHand,
      unit: 'mm',
      ref,
    },
  ]
  const messages: SafetyMessage[] = []
  if (rule.sWithWalk !== null) {
    steps.push({
      key: 'withWalkingSpeed',
      symbol: 'S',
      formula: `1600 · T + ${reachSymbol} + Z`,
      expression: '1600 · {t} + {reach} + {z}',
      args: { t, reach, z },
      value: rule.sWithWalk,
      unit: 'mm',
      ref,
    })
    messages.push({ code: 'walkingSpeedApplies', level: 'info', params: { limit: SWITCH_DISTANCE } })
  }
  const before = rule.sWithWalk ?? rule.sWithHand
  if (rule.floor !== null && rule.supplement > 0) {
    steps.push({
      key: 'minimumAndSupplement',
      symbol: 'S',
      formula: null,
      expression: 'max({s}, {floor}) + {supplement}',
      args: { s: before, floor: rule.floor, supplement: rule.supplement },
      value: rule.s,
      unit: 'mm',
      ref,
    })
  } else if (rule.floor !== null) {
    steps.push({
      key: 'minimum',
      symbol: 'S',
      formula: null,
      expression: 'max({s}, {floor})',
      args: { s: before, floor: rule.floor },
      value: rule.s,
      unit: 'mm',
      ref,
    })
  } else if (rule.supplement > 0) {
    steps.push({
      key: 'publicSupplement',
      symbol: 'S',
      formula: null,
      expression: '{s} + {supplement}',
      args: { s: before, supplement: rule.supplement },
      value: rule.s,
      unit: 'mm',
      ref,
    })
  }
  if (rule.floor !== null) messages.push({ code: 'minimumApplies', level: 'info', params: { min: rule.floor } })
  if (rule.supplement > 0) {
    messages.push({ code: 'publicSupplementApplies', level: 'info', params: { supplement: rule.supplement } })
  }
  return { steps, messages }
}
