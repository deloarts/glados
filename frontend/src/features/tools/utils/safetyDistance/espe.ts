import { approachSpeedRule, approachSpeedSteps, K_WALK } from './approachSpeed'
import {
  BEAM_HEIGHTS,
  BEAM_HEIGHTS_INDUSTRIAL,
  lookupByHazardHeight,
  lookupReachOver,
  REACH_OVER_TOP_EDGES,
  REACH_UNDER,
  REACH_UNDER_STRUCTURE,
} from './tables'
import type { BeamRow } from './tables'
import {
  lookupOpening,
  lookupStructure,
  MIN_STRUCTURE_HEIGHT,
  OPENINGS_UPPER,
  REACH_OVER_STRUCTURE,
  STRUCTURE_HEIGHT_WITHOUT_MEASURES,
} from './iso13857'
import type { CalcStep, CalcStepKey, EspeInputs, PathResult, SafetyMessage, StandardRef } from './types'

/** What one mode contributes to the result; the response time is added around it. */
export interface ModeOutcome {
  /** Symbol of the result when it is not S. */
  symbol?: string
  k: number | null
  s: number | null
  formula: string
  ref: StandardRef
  steps: CalcStep[]
  paths: PathResult[]
  messages: SafetyMessage[]
}

export const MIN_TOP_EDGE = 900
export const MAX_BOTTOM_EDGE = 300
export const MAX_STRUCTURE_GAP = 180
/** Up to this H_GB the reach under a structure comes from ISO 13857:2019, Table 4, as for a slot. */
export const ISO_13857_STRUCTURE_GAP = 120
export const RESTART_MAX_DETECTION = 30
/** How far above its minimum a restart distance is raised: the resolution of the result, 0.1 mm. */
export const RESTART_MARGIN = 0.1

export function missingOutcome(formula: string, ref: StandardRef): ModeOutcome {
  return {
    k: null,
    s: null,
    formula,
    ref,
    steps: [],
    paths: [],
    messages: [{ code: 'missingInputs', level: 'warning' }],
  }
}

function mmStep(
  key: CalcStepKey,
  symbol: string,
  value: number,
  ref: StandardRef | null,
  extra: Partial<Pick<CalcStep, 'formula' | 'expression' | 'args' | 'note'>> = {},
): CalcStep {
  return {
    key,
    symbol,
    formula: extra.formula ?? null,
    expression: extra.expression ?? null,
    args: extra.args ?? {},
    value,
    unit: 'mm',
    ref,
    ...(extra.note ? { note: extra.note } : {}),
  }
}

/** D_DT after 8.3.2 to 8.3.4; a d_e below 14 mm gives no reach through the field. */
export function reachThroughDistance(de: number): number {
  if (de <= 40) return Math.max(0, 8 * (de - 14))
  if (de <= 55) return 208 + 12 * (de - 40)
  return 850
}

function reachThroughStep(de: number): CalcStep {
  const value = reachThroughDistance(de)
  if (de <= 40) {
    return mmStep('reachThrough', 'D_DT', value, { clause: '8.3.2', equation: '18' }, {
      formula: 'max(8 · (d_e − 14), 0)',
      expression: 'max(8 · ({de} − 14), 0)',
      args: { de },
    })
  }
  if (de <= 55) {
    return mmStep('reachThrough', 'D_DT', value, { clause: '8.3.3', equation: '21' }, {
      formula: '208 + 12 · (d_e − 40)',
      expression: '208 + 12 · ({de} − 40)',
      args: { de },
    })
  }
  return mmStep('reachThrough', 'D_DT', value, { clause: '8.3.4', equation: '24' })
}

/** D_DU after 8.4.2 and 8.4.3, or null when H_DB exceeds 300 mm, which 8.4 does not permit. */
export function reachUnderDistance(de: number, bottomEdge: number, hazardHeight: number): number | null {
  if (bottomEdge > MAX_BOTTOM_EDGE) return null
  if (de + bottomEdge <= 40) return Math.max(0, 8 * (de + bottomEdge - 14))
  return lookupByHazardHeight(REACH_UNDER, hazardHeight).value
}

function reachOverStep(hazardHeight: number, topEdge: number): CalcStep | null {
  const lookup = lookupReachOver(hazardHeight, topEdge)
  if (!lookup) return null
  const column = REACH_OVER_TOP_EDGES[lookup.column] ?? 0
  let note: SafetyMessage | undefined
  if (lookup.rows.length === 2) {
    note = {
      code: 'reachOverRows',
      level: 'info',
      params: { column, lower: lookup.rows[0] ?? 0, upper: lookup.rows[1] ?? 0 },
    }
  } else if (!lookup.exact) {
    note = { code: 'reachOverColumn', level: 'info', params: { column } }
  }
  return mmStep('reachOver', 'D_DO', lookup.value, { clause: '8.2.2', table: '2' }, {
    args: { hh: hazardHeight, hdt: topEdge },
    note,
  })
}

function reachUnderStep(de: number, bottomEdge: number, hazardHeight: number): CalcStep {
  if (de + bottomEdge <= 40) {
    return mmStep('reachUnder', 'D_DU', Math.max(0, 8 * (de + bottomEdge - 14)), { clause: '8.4.2', equation: '27' }, {
      formula: 'max(8 · (d_e + H_DB − 14), 0)',
      expression: 'max(8 · ({de} + {hdb} − 14), 0)',
      args: { de, hdb: bottomEdge },
    })
  }
  const lookup = lookupByHazardHeight(REACH_UNDER, hazardHeight)
  return mmStep('reachUnder', 'D_DU', lookup.value, { clause: '8.4.3', table: '3' }, {
    note: lookup.exact ? undefined : { code: 'reachUnderRow', level: 'info', params: { row: lookup.row } },
  })
}

/**
 * Reach under a protective structure below the field (8.4.4). Up to 120 mm
 * the gap counts as a slot of width e = H_GB and D_GU comes from ISO
 * 13857:2019, Table 4; above, from Table 4 of ISO 13855.
 */
function reachUnderStructureStep(gap: number, hazardHeight: number): CalcStep {
  if (gap > ISO_13857_STRUCTURE_GAP) {
    const lookup = lookupByHazardHeight(REACH_UNDER_STRUCTURE, hazardHeight)
    return mmStep('reachUnderStructure', 'D_GU', lookup.value, { clause: '8.4.4', table: '4' }, {
      note: lookup.exact ? undefined : { code: 'reachUnderStructureRow', level: 'info', params: { row: lookup.row } },
    })
  }
  const slot = lookupOpening(OPENINGS_UPPER, 'slot', gap)
  return mmStep('reachUnderStructure', 'D_GU', slot?.value ?? 0, { standard: 'iso13857', clause: '4.2.4.1', table: '4' }, {
    args: { hgb: gap },
    note: { code: 'gapAsSlot', level: 'info' },
  })
}

/**
 * Reach over a protective structure above the field (8.2.3): D_GO from ISO
 * 13857:2019, Table 2, with the hazard height and the structure's top edge,
 * or null when the structure is lower than that table covers.
 */
function reachOverStructureStep(hazardHeight: number, structureTop: number): CalcStep | null {
  const lookup = lookupStructure(hazardHeight, structureTop, false)
  if (!lookup) return null
  const column = REACH_OVER_STRUCTURE.columns[lookup.column] ?? 0
  let note: SafetyMessage | undefined
  if (lookup.rows.length === 2) {
    note = {
      code: 'tableRows',
      level: 'info',
      params: { table: 2, column, lower: lookup.rows[0] ?? 0, upper: lookup.rows[1] ?? 0 },
    }
  } else if (!lookup.exact) {
    note = { code: 'tableColumn', level: 'info', params: { table: 2, column } }
  }
  return mmStep('reachOverStructure', 'D_GO', lookup.value, { standard: 'iso13857', clause: '4.2.2', table: '2' }, {
    args: { hh: hazardHeight, hgt: structureTop },
    note,
  })
}

const CURTAIN_FORMULA = 'S = K · T + D_DS + Z'
const CURTAIN_REF: StandardRef = { clause: '8.1', equation: '13' }

/**
 * A light curtain approached at a right angle (8.1 to 8.4, 8.6). Every way
 * past the field is calculated with its own approach speed rule. The
 * combined distance then applies the rule of the finer paths to the largest
 * reach distance D_DS, which is never smaller than any single path, and the
 * largest of all is the result.
 */
function curtain(inp: EspeInputs, t: number, z: number): ModeOutcome {
  const de = inp.detection
  const hh = inp.hazardHeight
  const topEdge = inp.topEdge
  const bottomEdge = inp.bottomEdge
  const needsTop = !inp.structureAbove
  const needsBottom = !inp.structureBelow
  if (
    de === null ||
    hh === null ||
    (needsTop && topEdge === null) ||
    (needsBottom && bottomEdge === null) ||
    (inp.structureAbove && inp.structureTop === null) ||
    (inp.structureBelow && inp.structureGap === null)
  ) {
    return missingOutcome(CURTAIN_FORMULA, CURTAIN_REF)
  }

  const messages: SafetyMessage[] = []
  const steps: CalcStep[] = []
  const paths: PathResult[] = []
  const reaches: { symbol: string; name: string; value: number }[] = []
  const publicArea = !inp.industrial
  const fine = de <= 55
  const ruleOptions = { fallback: !inp.restart, publicArea }

  if (topEdge !== null && bottomEdge !== null && topEdge <= bottomEdge) {
    messages.push({ code: 'edgesInverted', level: 'error' })
  }
  if (!fine) messages.push({ code: 'handNotDetected', level: 'warning' })
  if (inp.restart && de > RESTART_MAX_DETECTION) {
    messages.push({ code: 'restartResolution', level: 'error', params: { max: RESTART_MAX_DETECTION } })
  }

  // Reaching over the field, or over a structure that closes the space above it.
  if (inp.structureAbove) {
    const structureTop = inp.structureTop ?? 0
    const step = reachOverStructureStep(hh, structureTop)
    if (step) {
      steps.push(step)
      paths.push({ path: 'overStructure', ok: true, reach: step.value, k: null, s: step.value, ref: { clause: '8.2.3' } })
      if (structureTop < STRUCTURE_HEIGHT_WITHOUT_MEASURES) {
        messages.push({ code: 'structureTopLow', level: 'warning', params: { min: STRUCTURE_HEIGHT_WITHOUT_MEASURES } })
      }
    } else {
      messages.push({ code: 'structureTopTooLow', level: 'error', params: { min: MIN_STRUCTURE_HEIGHT } })
      paths.push({ path: 'overStructure', ok: false, reach: null, k: null, s: null, ref: { clause: '8.2.3' } })
    }
  } else {
    const step = reachOverStep(hh, topEdge ?? 0)
    if (step) {
      steps.push(step)
      reaches.push({ symbol: 'D_DO', name: 'over', value: step.value })
      const rule = approachSpeedRule(t, step.value, z, { fallback: true, publicArea: false })
      const equation = rule.sWithWalk === null ? '15' : '16'
      paths.push({ path: 'over', ok: true, reach: step.value, k: rule.k, s: rule.s, ref: { clause: '8.2.2', equation } })
    } else {
      messages.push({ code: 'topEdgeTooLow', level: 'error', params: { min: MIN_TOP_EDGE } })
      paths.push({ path: 'over', ok: false, reach: null, k: null, s: null, ref: { clause: '8.2.2', table: '2' } })
    }
  }

  // Reaching through the field.
  const through = reachThroughStep(de)
  steps.push(through)
  reaches.push({ symbol: 'D_DT', name: 'through', value: through.value })
  if (fine) {
    const rule = approachSpeedRule(t, through.value, z, ruleOptions)
    const walking = rule.sWithWalk !== null
    const ref: StandardRef =
      de <= 40
        ? { clause: '8.3.2', equation: walking ? '20' : '19' }
        : { clause: '8.3.3', equation: walking ? '23' : '22' }
    paths.push({ path: 'through', ok: true, reach: through.value, k: rule.k, s: rule.s, ref })
  } else {
    const s = K_WALK * t + through.value + z
    paths.push({ path: 'through', ok: true, reach: through.value, k: K_WALK, s, ref: through.ref as StandardRef })
  }

  // Reaching under the field, or under a structure below it.
  if (inp.structureBelow) {
    const gap = inp.structureGap ?? 0
    if (gap > MAX_STRUCTURE_GAP) {
      messages.push({ code: 'structureGapTooLarge', level: 'error', params: { max: MAX_STRUCTURE_GAP } })
      paths.push({ path: 'underStructure', ok: false, reach: null, k: null, s: null, ref: { clause: '8.4.4' } })
    } else {
      const step = reachUnderStructureStep(gap, hh)
      steps.push(step)
      paths.push({
        path: 'underStructure',
        ok: true,
        reach: step.value,
        k: null,
        s: step.value,
        ref: step.ref as StandardRef,
      })
    }
  } else if ((bottomEdge ?? 0) > MAX_BOTTOM_EDGE) {
    messages.push({ code: 'bottomEdgeTooHigh', level: 'error', params: { max: MAX_BOTTOM_EDGE } })
    paths.push({ path: 'under', ok: false, reach: null, k: null, s: null, ref: { clause: '8.4.1' } })
  } else {
    const step = reachUnderStep(de, bottomEdge ?? 0, hh)
    steps.push(step)
    reaches.push({ symbol: 'D_DU', name: 'under', value: step.value })
    const s = K_WALK * t + step.value + z
    paths.push({ path: 'under', ok: true, reach: step.value, k: K_WALK, s, ref: { clause: '8.4', equation: '26' } })
  }

  // Combined reach distance and the approach speed rule.
  const reach = Math.max(...reaches.map((r) => r.value))
  const reachArgs: Record<string, number> = {}
  for (const r of reaches) reachArgs[r.name] = r.value
  steps.push(
    mmStep('reachCombined', 'D_DS', reach, { clause: '8.1', equation: '13' }, {
      formula: reaches.length > 1 ? `max(${reaches.map((r) => r.symbol).join(', ')})` : null,
      expression: reaches.length > 1 ? `max(${reaches.map((r) => `{${r.name}}`).join(', ')})` : null,
      args: reachArgs,
    }),
  )

  let combined: number
  let k: number
  if (fine) {
    const rule = approachSpeedRule(t, reach, z, ruleOptions)
    const worked = approachSpeedSteps(rule, t, reach, z, 'D_DS', { clause: '8.2.2, 8.3.2' })
    steps.push(...worked.steps)
    messages.push(...worked.messages)
    combined = rule.s
    k = rule.k
  } else {
    combined = K_WALK * t + reach + z
    k = K_WALK
    steps.push(
      mmStep('withWalkingSpeed', 'S', combined, { clause: '8.3.4', equation: '24' }, {
        formula: '1600 · T + D_DS + Z',
        expression: '1600 · {t} + {reach} + {z}',
        args: { t, reach, z },
      }),
    )
  }

  // Protective structures set a minimum of their own.
  let s = combined
  const structures = paths.filter((p) => p.k === null && p.ok && p.s !== null)
  if (structures.some((p) => (p.s ?? 0) > combined)) {
    const args: Record<string, number> = { combined }
    for (const p of structures) args[p.path] = p.s ?? 0
    s = Math.max(combined, ...structures.map((p) => p.s ?? 0))
    steps.push(
      mmStep('separation', 'S', s, { clause: '8.1' }, {
        expression: `max(${Object.keys(args).map((name) => `{${name}}`).join(', ')})`,
        args,
      }),
    )
    messages.push({ code: 'structureGoverns', level: 'info' })
  }

  if (inp.restart && de <= RESTART_MAX_DETECTION) {
    const min = de <= 14 ? 100 : 150
    if (s <= min) {
      // S has to be more than the minimum, so it is raised to the next
      // value the result shows, one tenth of a millimetre above it.
      const raised = min + RESTART_MARGIN
      messages.push({ code: 'restartMinimumApplied', level: 'warning', params: { min, raised } })
      steps.push(
        mmStep('restartMinimum', 'S', raised, { clause: '8.6' }, {
          expression: 'max({s}, {min} + {margin})',
          args: { s, min, margin: RESTART_MARGIN },
        }),
      )
      s = raised
    } else {
      messages.push({ code: 'restartMinimumMet', level: 'info', params: { min } })
    }
  }

  const failed = messages.some((m) => m.level === 'error')
  return {
    k: failed ? null : k,
    s: failed ? null : s,
    formula: CURTAIN_FORMULA,
    ref: CURTAIN_REF,
    steps,
    paths,
    messages,
  }
}

function sameHeights(row: BeamRow, heights: readonly number[]): boolean {
  return row.positions.length === heights.length && row.positions.every((p, i) => p === heights[i])
}

/** The row of Annex C whose fixed beam heights equal the entered ones, C.1 before C.2. */
export function matchBeamRow(heights: readonly number[]): { table: 1 | 2; row: BeamRow } | null {
  const general = BEAM_HEIGHTS.find((row) => sameHeights(row, heights))
  if (general) return { table: 1, row: general }
  const industrial = BEAM_HEIGHTS_INDUSTRIAL.find((row) => sameHeights(row, heights))
  return industrial ? { table: 2, row: industrial } : null
}

const MULTI_BEAM_FORMULA = 'S = 1600 · T + D_DS + Z'
const MULTI_BEAM_REF: StandardRef = { clause: '8.3.5', equation: '24' }

/** Largest spacing between two beams, and the exception in front of a step (8.3.5). */
export const MAX_BEAM_SPACING = 400
export const STEP_BEAM_SPACING = 500
/** The step arrangement needs a step higher than this, and its upper level a foothold no wider than the next. */
export const MIN_STEP_HEIGHT = 300
export const MAX_STEP_FOOTHOLD = 50
/** In the step arrangement the lowest beam is at most this far above the upper level. */
export const STEP_LOWEST_BEAM = 200

/**
 * The checks of a beam arrangement on a level floor (4.5.3, 8.3.5, Annex C):
 * the lowest beam against crawling under, the top beam against stepping
 * over, the spacing against stepping through, and the rows of Annex C.
 * Returns whether two low beams protect a low opening, which leaves nothing
 * to reach over.
 */
function levelChecks(inp: EspeInputs, heights: number[], spacing: number, messages: SafetyMessage[]): boolean {
  const bottom = heights[0] as number
  const top = heights[heights.length - 1] as number
  if (bottom > 300 || (bottom > 200 && !inp.industrial)) {
    messages.push({ code: 'lowestBeamTooHigh', level: 'error', params: { max: inp.industrial ? 300 : 200 } })
  } else if (bottom > 200) {
    messages.push({ code: 'lowestBeamRiskAssessment', level: 'warning', params: { max: 200 } })
  }

  const match = matchBeamRow(heights)
  const lowOpening = match !== null && match.row.maxOpeningHeight !== undefined
  let lowOpeningAllowed = false
  if (top < MIN_TOP_EDGE) {
    const h = inp.openingHeight
    if (lowOpening && h !== null && h <= (match.row.maxOpeningHeight ?? 0)) {
      messages.push({ code: 'lowOpeningAllowed', level: 'info', params: { max: match.row.maxOpeningHeight ?? 0 } })
      lowOpeningAllowed = true
    } else {
      messages.push({ code: 'highestBeamTooLow', level: 'error', params: { min: MIN_TOP_EDGE } })
      if (lowOpening) {
        messages.push({ code: 'lowOpeningOnly', level: 'info', params: { max: match.row.maxOpeningHeight ?? 0 } })
      }
    }
  }

  if (spacing > MAX_BEAM_SPACING) {
    messages.push({
      code: 'beamSpacingTooLarge',
      level: 'error',
      params: { max: MAX_BEAM_SPACING, exception: STEP_BEAM_SPACING, step: MIN_STEP_HEIGHT },
    })
  }

  if (match) messages.push({ code: 'annexCMatch', level: 'info', params: { table: match.table, beams: match.row.beams } })
  else messages.push({ code: 'annexCNoMatch', level: 'warning' })
  return lowOpeningAllowed
}

/**
 * The two-beam arrangement in front of a step (8.3.5): reaching the hazard
 * needs a climb of more than 300 mm onto an upper level with no foothold
 * wider than 50 mm. Then two beams up to 500 mm apart may be used, the lowest
 * at most 200 mm above the upper level and the top one at least 900 mm above
 * the lower level, which the heights are measured from.
 */
function stepChecks(heights: number[], spacing: number, stepHeight: number, messages: SafetyMessage[]) {
  const bottom = heights[0] as number
  const top = heights[heights.length - 1] as number
  messages.push({ code: 'stepArrangement', level: 'info', params: { foothold: MAX_STEP_FOOTHOLD } })
  if (heights.length !== 2) messages.push({ code: 'stepTwoBeams', level: 'error' })
  if (stepHeight <= MIN_STEP_HEIGHT) messages.push({ code: 'stepTooLow', level: 'error', params: { min: MIN_STEP_HEIGHT } })
  if (bottom > stepHeight + STEP_LOWEST_BEAM) {
    messages.push({ code: 'stepLowestBeam', level: 'error', params: { max: stepHeight + STEP_LOWEST_BEAM, above: STEP_LOWEST_BEAM } })
  }
  if (top < MIN_TOP_EDGE) messages.push({ code: 'highestBeamTooLow', level: 'error', params: { min: MIN_TOP_EDGE } })
  if (spacing > STEP_BEAM_SPACING) {
    messages.push({ code: 'stepSpacingTooLarge', level: 'error', params: { max: STEP_BEAM_SPACING } })
  }
}

/**
 * A multi-beam device with d_e above 120 mm or undefined (8.3.5, Annex C).
 * It only detects a whole body, so the beams must stop a person crawling
 * under, stepping over or stepping between them. Through the beams the
 * reach is a full arm, 850 mm. Reaching over the top beam is checked with
 * Table 2 like over a light curtain, with the top beam as H_DT, and the
 * larger reach sets S, since D_DS is the largest of all paths (8.1). The
 * reach under the lowest beam never exceeds 850 mm (Table 3).
 */
function multiBeam(inp: EspeInputs, t: number, z: number): ModeOutcome {
  const heights = [...new Set(inp.beamHeights)].sort((a, b) => a - b)
  if (heights.length === 0 || (inp.stepArrangement && inp.stepHeight === null)) {
    return missingOutcome(MULTI_BEAM_FORMULA, MULTI_BEAM_REF)
  }
  const messages: SafetyMessage[] = [{ code: 'wholeBodyOnly', level: 'info' }]
  if (heights.length < 2) {
    messages.push({ code: 'tooFewBeams', level: 'error' })
    return { ...missingOutcome(MULTI_BEAM_FORMULA, MULTI_BEAM_REF), messages }
  }

  const bottom = heights[0] as number
  const top = heights[heights.length - 1] as number
  const spacing = Math.max(...heights.slice(1).map((h, i) => h - (heights[i] as number)))
  const ref: StandardRef = { clause: '8.3.5' }
  const steps: CalcStep[] = [
    mmStep('lowestBeam', 'H_DB', bottom, ref),
    mmStep('highestBeam', 'H_DT', top, ref),
    mmStep('beamSpacing', 'Δh', spacing, ref),
  ]

  let nothingToReachOver = false
  if (inp.stepArrangement) stepChecks(heights, spacing, inp.stepHeight ?? 0, messages)
  else nothingToReachOver = levelChecks(inp, heights, spacing, messages)

  // Reaching over the top beam, unless the beams are too low to be covered
  // at all (an error above) or guard a low opening.
  const reaches: { symbol: string; name: string; value: number }[] = [{ symbol: 'D_DT', name: 'through', value: 850 }]
  steps.push(mmStep('reachThrough', 'D_DT', 850, MULTI_BEAM_REF))
  if (!nothingToReachOver && top >= MIN_TOP_EDGE) {
    if (inp.hazardHeight === null) {
      return { ...missingOutcome(MULTI_BEAM_FORMULA, MULTI_BEAM_REF), messages: [...messages, { code: 'missingInputs', level: 'warning' }] }
    }
    const over = reachOverStep(inp.hazardHeight, top)
    if (over) {
      steps.push(over)
      reaches.unshift({ symbol: 'D_DO', name: 'over', value: over.value })
    }
  }
  const reach = Math.max(...reaches.map((r) => r.value))
  if (reaches.length > 1) {
    const args: Record<string, number> = {}
    for (const r of reaches) args[r.name] = r.value
    steps.push(
      mmStep('reachCombined', 'D_DS', reach, { clause: '8.1', equation: '13' }, {
        formula: `max(${reaches.map((r) => r.symbol).join(', ')})`,
        expression: `max(${reaches.map((r) => `{${r.name}}`).join(', ')})`,
        args,
      }),
    )
  }

  const s = K_WALK * t + reach + z
  steps.push(
    mmStep('separation', 'S', s, MULTI_BEAM_REF, {
      formula: '1600 · T + D_DS + Z',
      expression: '1600 · {t} + {reach} + {z}',
      args: { t, reach, z },
    }),
  )
  const failed = messages.some((m) => m.level === 'error')
  return {
    k: failed ? null : K_WALK,
    s: failed ? null : s,
    formula: MULTI_BEAM_FORMULA,
    ref: MULTI_BEAM_REF,
    steps,
    paths: [],
    messages,
  }
}

const SINGLE_BEAM_FORMULA = 'S = 1600 · T + 1200 + Z'
const SINGLE_BEAM_REF: StandardRef = { clause: '8.5', equation: '29' }

/** A single beam, which counts as an orthogonal approach in every case (8.5). */
function singleBeam(t: number, z: number): ModeOutcome {
  const s = K_WALK * t + 1200 + z
  return {
    k: K_WALK,
    s,
    formula: SINGLE_BEAM_FORMULA,
    ref: SINGLE_BEAM_REF,
    steps: [
      mmStep('separation', 'S', s, SINGLE_BEAM_REF, {
        formula: '1600 · T + 1200 + Z',
        expression: '1600 · {t} + 1200 + {z}',
        args: { t, z },
      }),
    ],
    paths: [],
    messages: [{ code: 'singleBeamPlacement', level: 'info' }],
  }
}

/** Separation distance of electro-sensitive protective equipment approached at a right angle (clause 8). */
export function calculateEspe(inp: EspeInputs, t: number | null, z: number): ModeOutcome {
  if (inp.device === 'singleBeam') return t === null ? missingOutcome(SINGLE_BEAM_FORMULA, SINGLE_BEAM_REF) : singleBeam(t, z)
  if (inp.device === 'multiBeam') return t === null ? missingOutcome(MULTI_BEAM_FORMULA, MULTI_BEAM_REF) : multiBeam(inp, t, z)
  return t === null ? missingOutcome(CURTAIN_FORMULA, CURTAIN_REF) : curtain(inp, t, z)
}
