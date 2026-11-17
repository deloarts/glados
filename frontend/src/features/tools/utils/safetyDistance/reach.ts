/**
 * The modes that need no response time: reaching over a protective
 * structure and reaching through an opening after ISO 13857:2019, and the
 * minimum gap at a crushing point after ISO 13854:2017. Their result is a
 * distance read from a table, checked against the distance as built when
 * the user enters one.
 */
import { missingOutcome } from './espe'
import type { ModeOutcome } from './espe'
import { MINIMUM_GAPS, TOE_STEP_DEPTH } from './iso13854'
import {
  lookupOpening,
  lookupStructure,
  lowestStructureHeight,
  MIN_STRUCTURE_HEIGHT,
  OPENINGS_CHILDREN,
  OPENINGS_LOWER,
  OPENINGS_UPPER,
  OUT_OF_REACH_HEIGHT,
  REACH_OVER_STRUCTURE,
  REACH_OVER_STRUCTURE_LOW_RISK,
  STRUCTURE_HEIGHT_WITHOUT_MEASURES,
  tableLimit,
  wholeBodyLimit,
} from './iso13857'
import type { OpeningTable } from './iso13857'
import type { ReachOverLookup } from './tables'
import type {
  CalcStep,
  CalcStepKey,
  CrushingInputs,
  OpeningInputs,
  SafetyMessage,
  StandardRef,
  StructureInputs,
} from './types'

function step(
  key: CalcStepKey,
  symbol: string,
  value: number,
  ref: StandardRef,
  extra: Partial<Pick<CalcStep, 'args' | 'note'>> = {},
): CalcStep {
  return {
    key,
    symbol,
    formula: null,
    expression: null,
    args: extra.args ?? {},
    value,
    unit: 'mm',
    ref,
    ...(extra.note ? { note: extra.note } : {}),
  }
}

function result(symbol: string, s: number | null, ref: StandardRef, steps: CalcStep[], messages: SafetyMessage[]): ModeOutcome {
  const failed = messages.some((m) => m.level === 'error' && !AS_BUILT_CHECKS.has(m.code))
  return { symbol, k: null, s: failed ? null : s, formula: '', ref, steps, paths: [], messages }
}

/**
 * Checks of the distance as built. They fail the design, not the
 * calculation, so the required distance stays visible next to them.
 */
const AS_BUILT_CHECKS = new Set(['structureTooClose', 'openingTooClose', 'gapTooSmall'])

/** Note on a reach-over lookup that left the grid of a table of ISO 13857. */
function gridNote(lookup: ReachOverLookup, columns: readonly number[], table: number): SafetyMessage | undefined {
  const column = columns[lookup.column] ?? 0
  if (lookup.rows.length === 2) {
    return { code: 'tableRows', level: 'info', params: { table, column, lower: lookup.rows[0] ?? 0, upper: lookup.rows[1] ?? 0 } }
  }
  if (!lookup.exact) return { code: 'tableColumn', level: 'info', params: { table, column } }
  return undefined
}

/**
 * Reaching over a protective structure (ISO 13857:2019, 4.2.2). Table 2
 * applies unless severity and probability of harm are both low, then Table 1
 * may be used. A hazard high enough cannot be reached at all (4.2.1). With a
 * distance as built the tool also names the lowest structure that is enough
 * at that distance (Annex A, example 1).
 */
export function calculateStructure(inp: StructureInputs): ModeOutcome {
  const table = inp.lowRisk ? 1 : 2
  const grid = inp.lowRisk ? REACH_OVER_STRUCTURE_LOW_RISK : REACH_OVER_STRUCTURE
  const ref: StandardRef = { standard: 'iso13857', clause: '4.2.2', table: String(table) }
  const hh = inp.hazardHeight
  const hps = inp.structureHeight
  if (hh === null || hps === null) return { ...missingOutcome('', ref), symbol: 's_h' }

  const messages: SafetyMessage[] = []
  if (inp.lowRisk) messages.push({ code: 'lowRiskTable', level: 'warning' })
  const lookup = lookupStructure(hh, hps, inp.lowRisk)
  if (!lookup) {
    messages.push({ code: 'structureTooLow', level: 'error', params: { min: MIN_STRUCTURE_HEIGHT } })
    return result('s_h', null, ref, [], messages)
  }
  if (!inp.lowRisk && hps < STRUCTURE_HEIGHT_WITHOUT_MEASURES) {
    messages.push({ code: 'structureLow', level: 'warning', params: { min: STRUCTURE_HEIGHT_WITHOUT_MEASURES } })
  }
  const outOfReach = grid.rows[0]?.hazardHeight ?? OUT_OF_REACH_HEIGHT
  if (hh >= outOfReach) messages.push({ code: 'outOfReachAbove', level: 'info', params: { height: outOfReach } })

  const sh = lookup.value
  const steps = [
    step('horizontalDistance', 's_h', sh, ref, { args: { hh, hps }, note: gridNote(lookup, grid.columns, table) }),
  ]
  if (inp.distance !== null) {
    const lowest = lowestStructureHeight(hh, inp.distance, inp.lowRisk)
    if (lowest !== null) {
      steps.push(step('minStructureHeight', 'h_{ps,min}', lowest, ref, { args: { distance: inp.distance } }))
    }
    if (inp.distance < sh) {
      messages.push({ code: 'structureTooClose', level: 'error', params: { min: sh } })
      if (lowest !== null) messages.push({ code: 'structureHeightForDistance', level: 'info', params: { height: lowest } })
    } else {
      messages.push({ code: 'distanceMet', level: 'info', params: { min: sh } })
    }
  }
  return result('s_h', sh, ref, steps, messages)
}

export function openingTable(inp: Pick<OpeningInputs, 'limb' | 'children'>): OpeningTable {
  if (inp.limb === 'lower') return OPENINGS_LOWER
  return inp.children ? OPENINGS_CHILDREN : OPENINGS_UPPER
}

/**
 * Reaching through a regular opening (ISO 13857:2019, 4.2.4 and 4.3). Table 4
 * applies from 14 years on, Table 5 where children from 3 years on may reach
 * the opening, Table 7 where only the lower limbs can. Openings beyond the
 * upper limb tables have to be treated as reaching over (4.2.2); slots above
 * 180 mm and other openings above 240 mm let the whole body through (4.4).
 */
export function calculateOpening(inp: OpeningInputs): ModeOutcome {
  const table = openingTable(inp)
  const ref: StandardRef = { standard: 'iso13857', clause: table.clause, table: table.table }
  const e = inp.size
  if (e === null) return { ...missingOutcome('', ref), symbol: 's_r' }

  const messages: SafetyMessage[] = []
  if (inp.limb === 'lower') messages.push({ code: 'lowerLimbsOnly', level: 'info' })
  else if (inp.children) messages.push({ code: 'childrenTable', level: 'info' })

  const wholeBody = wholeBodyLimit(inp.shape)
  const lookup = lookupOpening(table, inp.shape, e, inp.shape === 'slot' ? inp.slotLength : null)
  if (!lookup) {
    if (inp.limb === 'upper') {
      messages.push({ code: 'openingBeyondTable', level: 'error', params: { max: tableLimit(table) } })
    }
    if (e > wholeBody || inp.limb === 'lower') {
      messages.push({ code: 'openingWholeBodyAccess', level: 'error', params: { limit: wholeBody } })
    }
    return result('s_r', null, ref, [], messages)
  }
  if (lookup.value === null) {
    messages.push({ code: 'slotNotPermitted', level: 'error', params: { limit: wholeBody } })
    return result('s_r', null, ref, [], messages)
  }

  const sr = lookup.value
  const note: SafetyMessage | undefined = lookup.reduced
    ? { code: 'shortSlotReduction', level: 'info', params: { length: table.shortSlot.maxLength, value: table.shortSlot.value } }
    : undefined
  const steps = [step('openingReach', 's_r', sr, ref, { args: { e }, note })]
  if (inp.distance !== null) {
    if (inp.distance < sr) messages.push({ code: 'openingTooClose', level: 'error', params: { min: sr } })
    else messages.push({ code: 'distanceMet', level: 'info', params: { min: sr } })
  }
  return result('s_r', sr, ref, steps, messages)
}

/**
 * Minimum gap at a crushing point (ISO 13854:2017, Table 1) for the largest
 * body part that can get in, checked against the gap as built.
 */
export function calculateCrushing(inp: CrushingInputs): ModeOutcome {
  const ref: StandardRef = { standard: 'iso13854', clause: '4.2', table: '1' }
  if (inp.bodyPart === null) return { ...missingOutcome('', ref), symbol: 'a' }
  const a = MINIMUM_GAPS[inp.bodyPart]
  const messages: SafetyMessage[] = [{ code: 'largestBodyPart', level: 'info' }]
  if (inp.bodyPart === 'toes') messages.push({ code: 'toesOverhang', level: 'info', params: { depth: TOE_STEP_DEPTH } })
  if (inp.gap !== null) {
    if (inp.gap < a) messages.push({ code: 'gapTooSmall', level: 'error', params: { min: a } })
    else messages.push({ code: 'gapLargeEnough', level: 'info', params: { min: a } })
  }
  return result('a', a, ref, [step('minimumGap', 'a', a, ref)], messages)
}
