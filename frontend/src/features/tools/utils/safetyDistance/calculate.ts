import { calculateGuard, calculateHoldToRun, calculateParallel, calculateTwoHand } from './devices'
import { calculateEspe } from './espe'
import type { ModeOutcome } from './espe'
import { calculateCrushing, calculateOpening, calculateStructure } from './reach'
import { calculateResponseTime } from './responseTime'
import { modeGroup } from './types'
import type { ResponseTimeResult, SafetyDistanceInputs, SafetyDistanceResult } from './types'

/** Whether the mode's formula carries the supplement Z (5.6). */
export function usesSupplement(inputs: SafetyDistanceInputs): boolean {
  return inputs.mode === 'espe' || inputs.mode === 'parallel'
}

/** Whether the mode needs the response time T: the protective devices of ISO 13855 do, fixed distances do not. */
export function usesResponseTime(inputs: SafetyDistanceInputs): boolean {
  return modeGroup(inputs.mode) === 'devices'
}

function modeOutcome(inputs: SafetyDistanceInputs, t: number | null, z: number): ModeOutcome {
  switch (inputs.mode) {
    case 'espe':
      return calculateEspe(inputs.espe, t, z)
    case 'parallel':
      return calculateParallel(inputs.parallel, t, z)
    case 'twoHand':
      return calculateTwoHand(inputs.twoHand, t)
    case 'holdToRun':
      return calculateHoldToRun(inputs.holdToRun, t)
    case 'guard':
      return calculateGuard(inputs.guard, t)
    case 'structure':
      return calculateStructure(inputs.structure)
    case 'opening':
      return calculateOpening(inputs.opening)
    case 'crushing':
      return calculateCrushing(inputs.crushing)
  }
}

/** The response time of a mode that does not use one: nothing to show and nothing missing. */
function unusedResponseTime(inputs: SafetyDistanceInputs): ResponseTimeResult {
  return { method: inputs.responseTime.method, t: null, steps: [], conditions: [], messages: [] }
}

/**
 * The distance for the selected mode. An empty supplement counts as zero.
 * Without a response time a protective device has no distance. When T is
 * the only gap the user is asked for T; when other fields are empty as well,
 * one general request to fill in the fields replaces it. The modes without T
 * ignore the response time inputs entirely.
 */
export function calculateSafetyDistance(inputs: SafetyDistanceInputs): SafetyDistanceResult {
  if (!usesResponseTime(inputs)) {
    const outcome = modeOutcome(inputs, null, 0)
    return {
      mode: inputs.mode,
      symbol: outcome.symbol ?? 'S',
      responseTime: unusedResponseTime(inputs),
      t: null,
      supplement: null,
      k: null,
      s: outcome.s,
      formula: outcome.formula,
      ref: outcome.ref,
      steps: outcome.steps,
      paths: outcome.paths,
      messages: outcome.messages,
    }
  }
  const responseTime = calculateResponseTime(inputs.responseTime)
  const t = responseTime.t
  const z = usesSupplement(inputs) ? (inputs.supplement ?? 0) : null
  const outcome = modeOutcome(inputs, t, z ?? 0)
  let messages = [...responseTime.messages, ...outcome.messages]
  if (t === null) {
    // Calculating with a stand-in time shows whether anything besides T is missing.
    const othersMissing = modeOutcome(inputs, 0, z ?? 0).messages.some((m) => m.code === 'missingInputs')
    const rest = outcome.messages.filter((m) => m.code !== 'missingInputs')
    messages = othersMissing
      ? [{ code: 'missingInputs', level: 'warning' }, ...rest]
      : [...responseTime.messages, ...rest]
  }
  return {
    mode: inputs.mode,
    symbol: outcome.symbol ?? 'S',
    responseTime,
    t,
    supplement: z,
    k: outcome.k,
    s: t === null ? null : outcome.s,
    formula: outcome.formula,
    ref: outcome.ref,
    steps: outcome.steps,
    paths: outcome.paths,
    messages,
  }
}

function usedModeInputs(inputs: SafetyDistanceInputs): Record<string, unknown> {
  if (inputs.mode === 'espe') {
    const e = inputs.espe
    if (e.device === 'singleBeam') return { device: e.device }
    if (e.device === 'multiBeam') {
      return {
        device: e.device,
        beamHeights: [...e.beamHeights],
        hazardHeight: e.hazardHeight,
        industrial: e.industrial,
        ...(e.stepArrangement ? { stepArrangement: true, stepHeight: e.stepHeight } : { openingHeight: e.openingHeight }),
      }
    }
    return {
      device: e.device,
      detection: e.detection,
      topEdge: e.topEdge,
      bottomEdge: e.bottomEdge,
      hazardHeight: e.hazardHeight,
      industrial: e.industrial,
      restart: e.restart,
      structureAbove: e.structureAbove,
      structureTop: e.structureTop,
      structureBelow: e.structureBelow,
      structureGap: e.structureGap,
    }
  }
  if (inputs.mode === 'parallel') return { ...inputs.parallel }
  if (inputs.mode === 'twoHand') return { ...inputs.twoHand }
  if (inputs.mode === 'holdToRun') return { ...inputs.holdToRun }
  if (inputs.mode === 'structure') return { ...inputs.structure }
  if (inputs.mode === 'opening') return { ...inputs.opening }
  if (inputs.mode === 'crushing') return { ...inputs.crushing }
  const g = inputs.guard
  return {
    locking: g.locking,
    ...(g.locking ? { unlockDelay: g.unlockDelay } : {}),
    reachThroughOwn: g.reachThroughOwn,
    ...(g.reachThroughOwn ? { reachThrough: g.reachThrough } : {}),
    openingMethod: g.openingMethod,
    ...(g.openingMethod === 'direct'
      ? { openingShape: g.openingShape, slotLength: g.slotLength, opening: g.opening }
      : { guardWidth: g.guardWidth, angle: g.angle, guardThickness: g.guardThickness }),
  }
}

function usedResponseTimeInputs(inputs: SafetyDistanceInputs): Record<string, unknown> {
  const rt = inputs.responseTime
  if (rt.method === 'direct') return { method: rt.method, t: rt.direct }
  if (rt.method === 'measured') return { method: rt.method, cold: [...rt.cold], warm: [...rt.warm], tF: rt.tF }
  return { method: rt.method, tI: rt.tI, tL: rt.tL, tO: rt.tO, tD: rt.tD, tR: rt.tR, tM: rt.tM, tF: rt.tF, tS: rt.tS }
}

/**
 * The plain record saved with a calculation: the inputs that were used, every
 * intermediate value by step, the result of each reach path, K, S and the
 * findings. Numbers are stored as calculated, independent of any number
 * format, so reopening can compare them.
 */
export function safetyDistanceSnapshot(
  inputs: SafetyDistanceInputs,
  result: SafetyDistanceResult,
): Record<string, unknown> {
  const values: Record<string, number> = {}
  for (const step of [...result.responseTime.steps, ...result.steps]) values[step.key] = step.value
  const used = usesResponseTime(inputs)
    ? { ...usedModeInputs(inputs), responseTime: usedResponseTimeInputs(inputs), supplement: result.supplement }
    : usedModeInputs(inputs)
  return {
    mode: result.mode,
    inputs: used,
    responseTime: {
      method: result.responseTime.method,
      t: result.t,
      conditions: result.responseTime.conditions.map((c) => ({ ...c })),
    },
    values,
    paths: result.paths.map(({ path, ok, reach, k, s }) => ({ path, ok, reach, k, s })),
    k: result.k,
    s: result.s,
    messages: result.messages.map((m) => (m.params ? { code: m.code, level: m.level, params: { ...m.params } } : { code: m.code, level: m.level })),
  }
}
