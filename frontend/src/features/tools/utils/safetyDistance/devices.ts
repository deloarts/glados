import { K_WALK } from './approachSpeed'
import { missingOutcome } from './espe'
import type { ModeOutcome } from './espe'
import { lookupOpening, OPENINGS_UPPER, tableLimit, wholeBodyLimit } from './iso13857'
import { hingeGap } from './tables'
import type {
  CalcStep,
  CalcStepKey,
  GuardInputs,
  HoldToRunInputs,
  OpeningShape,
  ParallelInputs,
  SafetyMessage,
  SafetyMessageCode,
  StandardRef,
  TwoHandInputs,
  TwoHandType,
} from './types'

export const MAX_FIELD_HEIGHT = 1000
/** Above this height a person may crawl under a parallel field unnoticed (9.2). */
export const FIELD_HEIGHT_WARNING = 200
/** A gap this deep behind the field gives a foothold to step over it (9.4). */
export const FOOTHOLD_GAP = 70
/** Openings above this size let other body parts through (12.2.2); the whole body limit depends on the shape. */
export const OPENING_BODY_PARTS = 120

/** Clear distances between the actuators of a two-hand control (ISO 13851:2019, 7.2 and 7.3). */
export const ACTUATOR_GAP_ONE_HAND = 260
export const ACTUATOR_GAP_ELBOW = 550
export const ACTUATOR_GAP_ERGONOMIC = 600

function step(
  key: CalcStepKey,
  symbol: string,
  value: number,
  ref: StandardRef | null,
  extra: Partial<Pick<CalcStep, 'formula' | 'expression' | 'args' | 'unit'>> = {},
): CalcStep {
  return {
    key,
    symbol,
    formula: extra.formula ?? null,
    expression: extra.expression ?? null,
    args: extra.args ?? {},
    value,
    unit: extra.unit ?? 'mm',
    ref,
  }
}

function outcome(
  k: number,
  s: number,
  formula: string,
  ref: StandardRef,
  steps: CalcStep[],
  messages: SafetyMessage[],
): ModeOutcome {
  const failed = messages.some((m) => m.level === 'error')
  return { k: failed ? null : k, s: failed ? null : s, formula, ref, steps, paths: [], messages }
}

/** Lowest permitted height of a parallel field for a given d_e (9.2, equation 30). */
export function minimumFieldHeight(de: number): number {
  return Math.max(0, 15 * (de - 50))
}

/**
 * Required depth F_D of a parallel field (9.4). 900 mm are enough only when
 * there is no foothold of 70 mm or more behind the field and a person
 * standing in it is detected; otherwise, and when the gap is unknown, the
 * field has to be 1200 mm deep.
 */
export function requiredFieldDepth(obstacleGap: number | null, standingDetected: boolean): number {
  return obstacleGap !== null && obstacleGap < FOOTHOLD_GAP && standingDetected ? 900 : 1200
}

const PARALLEL_FORMULA = 'S = 1600 · T + 1200 + Z'
const PARALLEL_REF: StandardRef = { clause: '9.3', equation: '31' }

/** A detection zone approached in parallel, such as a mat or a horizontal light curtain (clause 9). */
export function calculateParallel(inp: ParallelInputs, t: number | null, z: number): ModeOutcome {
  const de = inp.detection
  const hd = inp.fieldHeight
  if (t === null || de === null || hd === null) return missingOutcome(PARALLEL_FORMULA, PARALLEL_REF)
  const messages: SafetyMessage[] = []
  const minHeight = minimumFieldHeight(de)
  const steps: CalcStep[] = [
    step('minFieldHeight', 'H_{D,min}', minHeight, { clause: '9.2', equation: '30' }, {
      formula: 'max(15 · (d_e − 50), 0)',
      expression: 'max(15 · ({de} − 50), 0)',
      args: { de },
    }),
  ]
  if (minHeight > MAX_FIELD_HEIGHT) {
    messages.push({ code: 'detectionTooCoarse', level: 'error', params: { max: MAX_FIELD_HEIGHT } })
  } else if (hd < minHeight) {
    messages.push({ code: 'fieldTooLow', level: 'error', params: { min: minHeight } })
  }
  if (hd > MAX_FIELD_HEIGHT) {
    messages.push({ code: 'fieldTooHigh', level: 'error', params: { max: MAX_FIELD_HEIGHT } })
  } else if (hd > FIELD_HEIGHT_WARNING) {
    messages.push({ code: 'fieldAboveCrawlHeight', level: 'warning', params: { limit: FIELD_HEIGHT_WARNING } })
  }

  const s = K_WALK * t + 1200 + z
  steps.push(
    step('separation', 'S', s, PARALLEL_REF, {
      formula: '1600 · T + 1200 + Z',
      expression: '1600 · {t} + 1200 + {z}',
      args: { t, z },
    }),
  )

  const depth = requiredFieldDepth(inp.obstacleGap, inp.standingDetected)
  steps.push(step('requiredDepth', 'F_{D,min}', depth, { clause: '9.4' }))
  if (inp.fieldDepth !== null && inp.fieldDepth < depth) {
    messages.push({ code: 'fieldTooShallow', level: 'error', params: { min: depth } })
  }
  if (depth === 1200 && inp.obstacleGap !== null && inp.obstacleGap < FOOTHOLD_GAP) {
    messages.push({ code: 'depthReducible', level: 'info', params: { depth: 900 } })
  }
  messages.push({ code: 'farthestEdge', level: 'info' })
  return outcome(K_WALK, s, PARALLEL_FORMULA, PARALLEL_REF, steps, messages)
}

const TYPE_MESSAGES: Record<TwoHandType, SafetyMessage> = {
  I: { code: 'twoHandTypeI', level: 'warning' },
  II: { code: 'twoHandTypeII', level: 'info' },
  IIIA: { code: 'twoHandTypeIIIA', level: 'info' },
  IIIB: { code: 'twoHandTypeIIIB', level: 'info' },
  IIIC: { code: 'twoHandTypeIIIC', level: 'info' },
}

/**
 * What ISO 13851:2019 asks of the device itself: the minimum performance of
 * its type (Table 1) and the clear distance between the actuators against
 * defeat with one hand (7.2) or with hand and elbow of one arm (7.3). The
 * standard names the distances as examples of measures, partitions and
 * covers being others, so they give warnings and notes, not errors.
 */
export function twoHandChecks(inp: TwoHandInputs): SafetyMessage[] {
  const messages: SafetyMessage[] = []
  if (inp.type !== null) messages.push(TYPE_MESSAGES[inp.type])
  const gap = inp.actuatorGap
  if (gap !== null) {
    const code: SafetyMessageCode | null =
      gap < ACTUATOR_GAP_ONE_HAND
        ? 'actuatorGapOneHand'
        : gap < ACTUATOR_GAP_ELBOW
          ? 'actuatorGapElbow'
          : gap > ACTUATOR_GAP_ERGONOMIC
            ? 'actuatorGapErgonomic'
            : null
    if (code === 'actuatorGapOneHand') {
      messages.push({ code, level: 'warning', params: { min: ACTUATOR_GAP_ONE_HAND, elbow: ACTUATOR_GAP_ELBOW } })
    } else if (code === 'actuatorGapElbow') {
      messages.push({ code, level: 'warning', params: { min: ACTUATOR_GAP_ELBOW } })
    } else if (code === 'actuatorGapErgonomic') {
      messages.push({ code, level: 'info', params: { max: ACTUATOR_GAP_ERGONOMIC } })
    }
  }
  return messages
}

/** A two-hand control device, measured from its nearest actuator (clause 10). */
export function calculateTwoHand(inp: TwoHandInputs, t: number | null): ModeOutcome {
  const checks = twoHandChecks(inp)
  if (inp.encroachmentPrevented) {
    const formula = 'S = max(1600 · T, 100)'
    const ref: StandardRef = { clause: '10.2' }
    if (t === null) {
      const missing = missingOutcome(formula, ref)
      return { ...missing, messages: [...missing.messages, ...checks] }
    }
    const s = Math.max(K_WALK * t, 100)
    const messages: SafetyMessage[] = [{ code: 'encroachmentConfirm', level: 'info' }, ...checks]
    if (K_WALK * t < 100) messages.push({ code: 'minimumApplies', level: 'info', params: { min: 100 } })
    const steps = [
      step('separation', 'S', s, ref, {
        formula: 'max(1600 · T, 100)',
        expression: 'max(1600 · {t}, 100)',
        args: { t },
      }),
    ]
    return outcome(K_WALK, s, formula, ref, steps, messages)
  }
  const formula = 'S = 1600 · T + 550'
  const ref: StandardRef = { clause: '10.1', equation: '33' }
  if (t === null) {
    const missing = missingOutcome(formula, ref)
    return { ...missing, messages: [...missing.messages, ...checks] }
  }
  const s = K_WALK * t + 550
  const steps = [
    step('separation', 'S', s, ref, { formula: '1600 · T + 550', expression: '1600 · {t} + 550', args: { t } }),
  ]
  return outcome(K_WALK, s, formula, ref, steps, [{ code: 'measuredFromActuator', level: 'info' }, ...checks])
}

/** A single hand or foot operated control device such as a hold-to-run control (clause 11). */
export function calculateHoldToRun(inp: HoldToRunInputs, t: number | null): ModeOutcome {
  const reach = inp.actuation === 'foot' ? 2500 : 2200
  const ref: StandardRef = inp.actuation === 'foot' ? { clause: '11.2', equation: '35' } : { clause: '11.1', equation: '34' }
  const formula = `S = 1600 · T + ${reach}`
  if (t === null) return missingOutcome(formula, ref)
  const s = K_WALK * t + reach
  const steps = [
    step('separation', 'S', s, ref, {
      formula: `1600 · T + ${reach}`,
      expression: `1600 · {t} + ${reach}`,
      args: { t },
    }),
  ]
  return outcome(K_WALK, s, formula, ref, steps, [{ code: 'measuredFromActuator', level: 'info' }])
}

export interface HingeOpening {
  b: number
  /** e = b − G_T, never below zero. */
  e: number
  /** G_T exceeds b, so the leaf leaves no gap. */
  clamped: boolean
}

/**
 * Opening e of a hinged guard with a cam operated switch when the switch
 * trips (12.2.2, equations 38 to 40). A leaf thicker than the gap b leaves
 * no opening, so e is never negative.
 */
export function hingeOpening(guardWidth: number, angleDeg: number, thickness: number): HingeOpening {
  const b = hingeGap(guardWidth, angleDeg)
  return { b, e: Math.max(b - thickness, 0), clamped: b - thickness < 0 }
}

interface GuardOpening {
  steps: CalcStep[]
  messages: SafetyMessage[]
  e: number | null
  shape: OpeningShape
}

/** The opening e before the interlock trips and its shape; the gap of a hinged guard is a slot. */
function openingSteps(inp: GuardInputs): GuardOpening {
  const steps: CalcStep[] = []
  const messages: SafetyMessage[] = []
  const shape: OpeningShape = inp.openingMethod === 'hinged' ? 'slot' : inp.openingShape
  let e: number | null = null
  if (inp.openingMethod === 'hinged') {
    const gw = inp.guardWidth
    const angle = inp.angle
    const gt = inp.guardThickness
    if (gw !== null && angle !== null && gt !== null) {
      const opening = hingeOpening(gw, angle, gt)
      steps.push(
        step('hingeGap', 'b', opening.b, { clause: '12.2.2', equation: '39' }, {
          formula: 'G_W · sin ω',
          expression: '{gw} · sin {angle}°',
          args: { gw, angle },
        }),
        step('opening', 'e', opening.e, { clause: '12.2.2', equation: '40' }, {
          formula: 'max(b − G_T, 0)',
          expression: 'max({b} − {gt}, 0)',
          args: { b: opening.b, gt },
        }),
      )
      if (opening.clamped) messages.push({ code: 'openingClamped', level: 'info' })
      e = opening.e
    }
  } else if (inp.opening !== null) {
    e = inp.opening
    steps.push(step('opening', 'e', e, { clause: '12.2.1' }))
  }
  const wholeBody = wholeBodyLimit(shape)
  if (e !== null && e > wholeBody) {
    messages.push({ code: 'openingWholeBody', level: 'warning', params: { limit: wholeBody } })
  } else if (e !== null && e > OPENING_BODY_PARTS) {
    messages.push({ code: 'openingBodyParts', level: 'warning', params: { limit: OPENING_BODY_PARTS } })
  }
  return { steps, messages, e, shape }
}

/**
 * D_GT for the opening (12.2.1): from ISO 13857:2019, Table 4, for its size
 * and shape, or the user's own value where the risk assessment justifies
 * one. Table 4 ends at 120 mm; a larger opening needs an own value. Null
 * when a value is missing or the table does not cover the opening.
 */
function reachThroughGuard(inp: GuardInputs, opening: GuardOpening): { step: CalcStep | null; messages: SafetyMessage[] } {
  const ref: StandardRef = { standard: 'iso13857', clause: '4.2.4.1', table: '4' }
  const slotLength = inp.openingMethod === 'direct' && opening.shape === 'slot' ? inp.slotLength : null
  const table = opening.e === null ? null : lookupOpening(OPENINGS_UPPER, opening.shape, opening.e, slotLength)
  if (inp.reachThroughOwn) {
    if (inp.reachThrough === null) return { step: null, messages: [] }
    const messages: SafetyMessage[] = [{ code: 'reachThroughOwnValue', level: 'warning' }]
    if (table && table.value !== null && inp.reachThrough < table.value) {
      messages.push({ code: 'reachThroughOwnBelowTable', level: 'warning', params: { table: table.value } })
    }
    return { step: step('reachThroughGuard', 'D_GT', inp.reachThrough, { clause: '12.2.1' }), messages }
  }
  if (opening.e === null) return { step: null, messages: [] }
  if (!table || table.value === null) {
    return { step: null, messages: [{ code: 'guardOpeningBeyondTable', level: 'error', params: { max: tableLimit(OPENINGS_UPPER) } }] }
  }
  const note: SafetyMessage | undefined = table.reduced
    ? { code: 'shortSlotReduction', level: 'info', params: { length: OPENINGS_UPPER.shortSlot.maxLength, value: OPENINGS_UPPER.shortSlot.value } }
    : undefined
  const reach: CalcStep = { ...step('reachThroughGuard', 'D_GT', table.value, ref, { args: { e: opening.e } }), ...(note ? { note } : {}) }
  return { step: reach, messages: [] }
}

/**
 * An interlocking guard (clause 12). With guard locking only the part of T
 * that the unlocking delay does not cover counts. The standard covers the
 * case t_DY < T; a longer delay is read as leaving no time term, so S equals
 * D_GT, and the tool says so.
 */
export function calculateGuard(inp: GuardInputs, t: number | null): ModeOutcome {
  const formula = inp.locking ? 'S = 1600 · (T − t_DY) + D_GT' : 'S = 1600 · T + D_GT'
  const ref: StandardRef = inp.locking ? { clause: '12.3', equation: '41' } : { clause: '12.2.1', equation: '37' }
  const opening = openingSteps(inp)
  const reach = reachThroughGuard(inp, opening)
  const known = [...opening.messages, ...reach.messages]
  if (known.some((m) => m.level === 'error')) {
    return { k: null, s: null, formula, ref, steps: opening.steps, paths: [], messages: known }
  }
  const delay = inp.unlockDelay
  if (t === null || reach.step === null || (inp.locking && delay === null)) {
    const missing = missingOutcome(formula, ref)
    const steps = reach.step ? [...opening.steps, reach.step] : opening.steps
    return { ...missing, steps, messages: [...known, ...missing.messages] }
  }

  const dgt = reach.step.value
  const steps = [...opening.steps, reach.step]
  const messages = [...known]
  let s: number
  if (inp.locking) {
    const remaining = Math.max(t - (delay ?? 0), 0)
    if ((delay ?? 0) >= t) messages.push({ code: 'unlockDelayCoversT', level: 'warning' })
    s = K_WALK * remaining + dgt
    steps.push(
      step('remainingTime', 'T − t_DY', remaining, { clause: '12.3' }, {
        formula: 'max(T − t_DY, 0)',
        expression: 'max({t} − {delay}, 0)',
        args: { t, delay: delay ?? 0 },
        unit: 's',
      }),
      step('separation', 'S', s, ref, {
        formula: '1600 · (T − t_DY) + D_GT',
        expression: '1600 · {remaining} + {dgt}',
        args: { remaining, dgt },
      }),
    )
  } else {
    s = K_WALK * t + dgt
    steps.push(
      step('separation', 'S', s, ref, {
        formula: '1600 · T + D_GT',
        expression: '1600 · {t} + {dgt}',
        args: { t, dgt },
      }),
    )
  }
  messages.push({ code: 'measuredFromOpening', level: 'info' })
  return outcome(K_WALK, s, formula, ref, steps, messages)
}
