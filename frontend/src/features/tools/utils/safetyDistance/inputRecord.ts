import { emptySafetyDistanceInputs, LIMITS, MAX_BEAMS, MAX_SAMPLES, parseDecimal, withinLimit } from './inputs'
import type { FieldLimit } from './inputs'
import { usesResponseTime } from './calculate'
import {
  BODY_PARTS,
  ESPE_DEVICES,
  HOLD_TO_RUN_ACTUATIONS,
  LIMBS,
  OPENING_METHODS,
  OPENING_SHAPES,
  RESPONSE_TIME_COMPONENTS,
  RESPONSE_TIME_METHODS,
  SAFETY_DISTANCE_MODES,
  TWO_HAND_TYPES,
} from './types'
import type { ResponseTimeComponent, SafetyDistanceInputs } from './types'

/**
 * The inputs as a flat record of strings, the form a saved calculation stores
 * and hands back to the tab. Only the keys that the selected mode and
 * response time method use are written, so the record carries nothing that
 * does not affect its result, and encoding the decoded record gives the same
 * record again. Numbers use a dot as decimal separator, lists a comma.
 */

const COMPONENT_KEYS: Record<ResponseTimeComponent, string> = {
  tI: 'ti',
  tL: 'tl',
  tO: 'to',
  tD: 'td',
  tR: 'tr',
  tM: 'tm',
  tF: 'tf',
  tS: 'ts',
}

/** Every key the record may hold. */
export const SAFETY_DISTANCE_INPUT_KEYS = [
  'mode',
  'tmode',
  't',
  ...Object.values(COMPONENT_KEYS),
  'cold',
  'warm',
  'z',
  'dev',
  'de',
  'hdt',
  'hdb',
  'hh',
  'ind',
  'rs',
  'above',
  'hgt',
  'below',
  'hgb',
  'beams',
  'oh',
  'step',
  'hs',
  'hd',
  'fd',
  'gd',
  'stand',
  'prevent',
  'type',
  'gap',
  'act',
  'lock',
  'tdy',
  'own',
  'dgt',
  'em',
  'shape',
  'sl',
  'e',
  'gw',
  'w',
  'gt',
  'hps',
  'sh',
  'low',
  'limb',
  'kids',
  'sr',
  'part',
  'a',
] as const

function num(value: number | null): string {
  return value === null ? '' : String(value)
}

function flag(value: boolean): string {
  return value ? '1' : '0'
}

export function encodeSafetyDistanceInputs(inputs: SafetyDistanceInputs): Record<string, string> {
  const q: Record<string, string> = { mode: inputs.mode }
  const rt = inputs.responseTime
  if (usesResponseTime(inputs)) {
    q.tmode = rt.method
    if (rt.method === 'direct') q.t = num(rt.direct)
    if (rt.method === 'components') {
      for (const component of RESPONSE_TIME_COMPONENTS) q[COMPONENT_KEYS[component]] = num(rt[component])
    }
    if (rt.method === 'measured') {
      q.cold = rt.cold.join(',')
      q.warm = rt.warm.join(',')
      q.tf = num(rt.tF)
    }
  }

  if (inputs.mode === 'espe') {
    const e = inputs.espe
    q.z = num(inputs.supplement)
    q.dev = e.device
    if (e.device === 'curtain') {
      q.de = num(e.detection)
      q.hdt = num(e.topEdge)
      q.hdb = num(e.bottomEdge)
      q.hh = num(e.hazardHeight)
      q.ind = flag(e.industrial)
      q.rs = flag(e.restart)
      q.above = flag(e.structureAbove)
      if (e.structureAbove) q.hgt = num(e.structureTop)
      q.below = flag(e.structureBelow)
      if (e.structureBelow) q.hgb = num(e.structureGap)
    } else if (e.device === 'multiBeam') {
      q.beams = e.beamHeights.join(',')
      q.hh = num(e.hazardHeight)
      q.ind = flag(e.industrial)
      q.step = flag(e.stepArrangement)
      if (e.stepArrangement) q.hs = num(e.stepHeight)
      else q.oh = num(e.openingHeight)
    }
  } else if (inputs.mode === 'parallel') {
    const p = inputs.parallel
    q.z = num(inputs.supplement)
    q.de = num(p.detection)
    q.hd = num(p.fieldHeight)
    q.fd = num(p.fieldDepth)
    q.gd = num(p.obstacleGap)
    q.stand = flag(p.standingDetected)
  } else if (inputs.mode === 'twoHand') {
    const h = inputs.twoHand
    q.prevent = flag(h.encroachmentPrevented)
    q.type = h.type ?? ''
    q.gap = num(h.actuatorGap)
  } else if (inputs.mode === 'holdToRun') {
    q.act = inputs.holdToRun.actuation
  } else if (inputs.mode === 'structure') {
    const st = inputs.structure
    q.hh = num(st.hazardHeight)
    q.hps = num(st.structureHeight)
    q.sh = num(st.distance)
    q.low = flag(st.lowRisk)
  } else if (inputs.mode === 'opening') {
    const o = inputs.opening
    q.shape = o.shape
    q.e = num(o.size)
    if (o.shape === 'slot') q.sl = num(o.slotLength)
    q.limb = o.limb
    if (o.limb === 'upper') q.kids = flag(o.children)
    q.sr = num(o.distance)
  } else if (inputs.mode === 'crushing') {
    q.part = inputs.crushing.bodyPart ?? ''
    q.a = num(inputs.crushing.gap)
  } else {
    const g = inputs.guard
    q.lock = flag(g.locking)
    if (g.locking) q.tdy = num(g.unlockDelay)
    q.own = flag(g.reachThroughOwn)
    if (g.reachThroughOwn) q.dgt = num(g.reachThrough)
    q.em = g.openingMethod
    if (g.openingMethod === 'direct') {
      q.shape = g.openingShape
      if (g.openingShape === 'slot') q.sl = num(g.slotLength)
      q.e = num(g.opening)
    } else {
      q.gw = num(g.guardWidth)
      q.w = num(g.angle)
      q.gt = num(g.guardThickness)
    }
  }
  return q
}

/**
 * Reads a saved record, which may come from an older version of the tool. A
 * missing key leaves its field as the cleared form has it; a key that is
 * present but out of range or unreadable does the same and sets `invalid`,
 * so the tab can tell the user once. An empty value is an empty field. Unknown keys are
 * ignored.
 */
export function decodeSafetyDistanceInputs(record: Record<string, unknown>): {
  inputs: SafetyDistanceInputs
  invalid: boolean
} {
  const inputs = emptySafetyDistanceInputs()
  let invalid = false

  const raw = (key: string): string | undefined => {
    const value = record[key]
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    return undefined
  }
  const number = (key: string, limit: FieldLimit, fallback: number | null): number | null => {
    const value = raw(key)
    if (value === undefined) return fallback
    if (value.trim() === '') return null
    const parsed = parseDecimal(value.replace(',', '.'))
    if (withinLimit(parsed, limit)) return parsed
    invalid = true
    return fallback
  }
  const bool = (key: string, fallback: boolean): boolean => {
    const value = raw(key)
    if (value === undefined) return fallback
    if (value === '1' || value === '0') return value === '1'
    invalid = true
    return fallback
  }
  const choice = <T extends string>(key: string, options: readonly T[], fallback: T): T => {
    const value = raw(key)
    if (value === undefined) return fallback
    if ((options as readonly string[]).includes(value)) return value as T
    invalid = true
    return fallback
  }
  // A choice that may be left open; an empty value is no choice.
  const optionalChoice = <T extends string>(key: string, options: readonly T[], fallback: T | null): T | null => {
    const value = raw(key)
    if (value === undefined) return fallback
    if (value === '') return null
    if ((options as readonly string[]).includes(value)) return value as T
    invalid = true
    return fallback
  }
  const list = (key: string, limit: FieldLimit, maxCount: number, fallback: number[]): number[] => {
    const value = raw(key)
    if (value === undefined) return fallback
    if (value.trim() === '') return []
    const parts = value.split(',').map(parseDecimal)
    if (parts.length <= maxCount && parts.every((part) => withinLimit(part, limit))) return parts
    invalid = true
    return fallback
  }

  inputs.mode = choice('mode', SAFETY_DISTANCE_MODES, inputs.mode)
  const rt = inputs.responseTime
  rt.method = choice('tmode', RESPONSE_TIME_METHODS, rt.method)
  rt.direct = number('t', LIMITS.time, rt.direct)
  for (const component of RESPONSE_TIME_COMPONENTS) {
    rt[component] = number(COMPONENT_KEYS[component], LIMITS.time, rt[component])
  }
  rt.cold = list('cold', LIMITS.time, MAX_SAMPLES, rt.cold)
  rt.warm = list('warm', LIMITS.time, MAX_SAMPLES, rt.warm)
  inputs.supplement = number('z', LIMITS.length, inputs.supplement)

  if (inputs.mode === 'espe') {
    const e = inputs.espe
    e.device = choice('dev', ESPE_DEVICES, e.device)
    e.detection = number('de', LIMITS.detection, e.detection)
    e.topEdge = number('hdt', LIMITS.length, e.topEdge)
    e.bottomEdge = number('hdb', LIMITS.length, e.bottomEdge)
    e.hazardHeight = number('hh', LIMITS.length, e.hazardHeight)
    e.industrial = bool('ind', e.industrial)
    e.restart = bool('rs', e.restart)
    e.structureAbove = bool('above', e.structureAbove)
    e.structureTop = number('hgt', LIMITS.length, e.structureTop)
    e.structureBelow = bool('below', e.structureBelow)
    e.structureGap = number('hgb', LIMITS.length, e.structureGap)
    e.beamHeights = list('beams', LIMITS.length, MAX_BEAMS, e.beamHeights)
    e.openingHeight = number('oh', LIMITS.length, e.openingHeight)
    e.stepArrangement = bool('step', false)
    e.stepHeight = number('hs', LIMITS.length, null)
  } else if (inputs.mode === 'parallel') {
    const p = inputs.parallel
    p.detection = number('de', LIMITS.parallelDetection, p.detection)
    p.fieldHeight = number('hd', LIMITS.length, p.fieldHeight)
    p.fieldDepth = number('fd', LIMITS.length, p.fieldDepth)
    p.obstacleGap = number('gd', LIMITS.length, p.obstacleGap)
    p.standingDetected = bool('stand', p.standingDetected)
  } else if (inputs.mode === 'twoHand') {
    const h = inputs.twoHand
    h.encroachmentPrevented = bool('prevent', h.encroachmentPrevented)
    // Records written before these fields existed leave them open.
    h.type = optionalChoice('type', TWO_HAND_TYPES, null)
    h.actuatorGap = number('gap', LIMITS.length, null)
  } else if (inputs.mode === 'holdToRun') {
    inputs.holdToRun.actuation = choice('act', HOLD_TO_RUN_ACTUATIONS, inputs.holdToRun.actuation)
  } else if (inputs.mode === 'structure') {
    const st = inputs.structure
    st.hazardHeight = number('hh', LIMITS.length, st.hazardHeight)
    st.structureHeight = number('hps', LIMITS.length, st.structureHeight)
    st.distance = number('sh', LIMITS.length, st.distance)
    st.lowRisk = bool('low', st.lowRisk)
  } else if (inputs.mode === 'opening') {
    const o = inputs.opening
    o.shape = choice('shape', OPENING_SHAPES, o.shape)
    o.size = number('e', LIMITS.length, o.size)
    o.slotLength = number('sl', LIMITS.length, null)
    o.limb = choice('limb', LIMBS, o.limb)
    o.children = bool('kids', false)
    o.distance = number('sr', LIMITS.length, o.distance)
  } else if (inputs.mode === 'crushing') {
    const c = inputs.crushing
    c.bodyPart = optionalChoice('part', BODY_PARTS, c.bodyPart)
    c.gap = number('a', LIMITS.length, c.gap)
  } else {
    const g = inputs.guard
    g.locking = bool('lock', g.locking)
    g.unlockDelay = number('tdy', LIMITS.time, g.unlockDelay)
    g.reachThroughOwn = bool('own', g.reachThroughOwn)
    g.reachThrough = number('dgt', LIMITS.length, g.reachThrough)
    g.openingMethod = choice('em', OPENING_METHODS, g.openingMethod)
    g.openingShape = choice('shape', OPENING_SHAPES, g.openingShape)
    g.slotLength = number('sl', LIMITS.length, null)
    g.opening = number('e', LIMITS.length, g.opening)
    g.guardWidth = number('gw', LIMITS.length, g.guardWidth)
    g.angle = number('w', LIMITS.angle, g.angle)
    g.guardThickness = number('gt', LIMITS.length, g.guardThickness)
  }
  return { inputs, invalid }
}
