import {
  cell,
  dataTable,
  footnote,
  keepTogether,
  keyValueGrid,
  REPORT_EMPTY,
  section,
  subheading,
} from '@/shared/reports'
import type { Content, KeyValue } from '@/shared/reports'
import { usesSupplement } from './calculate'
import { formatQuantity } from './format'
import type { SafetyDistanceFormat } from './format'
import { F, labelled, P, quantity, rich, RT, yesNo } from './reportText'
import { RESPONSE_TIME_COMPONENTS } from './types'
import type { SafetyDistanceInputs, SafetyDistanceResult } from './types'

/** The inputs of the chosen mode and the response time, as the Safety Distance report lists them. */

function espeRows(inputs: SafetyDistanceInputs, f: SafetyDistanceFormat): KeyValue[] {
  const { t } = f
  const e = inputs.espe
  const rows: KeyValue[] = [{ label: t(`${P}.deviceLabel`), value: t(`${P}.devices.${e.device}`) }]
  const environment = { label: t(`${P}.environment.label`), value: t(`${P}.environment.${e.industrial ? 'industrial' : 'public'}`) }
  if (e.device === 'curtain') {
    rows.push(
      { label: labelled(t(`${F}.detection.label`), 'd_e'), value: quantity(e.detection, 'mm', f) },
      { label: labelled(t(`${F}.hazardHeight.label`), 'H_H'), value: quantity(e.hazardHeight, 'mm', f) },
      { label: labelled(t(`${F}.topEdge.label`), 'H_DT'), value: quantity(e.topEdge, 'mm', f) },
      { label: labelled(t(`${F}.bottomEdge.label`), 'H_DB'), value: quantity(e.bottomEdge, 'mm', f) },
      environment,
      { label: t(`${F}.restart.label`), value: yesNo(e.restart, t) },
      { label: t(`${F}.structureAbove.label`), value: yesNo(e.structureAbove, t) },
    )
    if (e.structureAbove) {
      rows.push({ label: labelled(t(`${F}.structureTop.label`), 'H_GT'), value: quantity(e.structureTop, 'mm', f) })
    }
    rows.push({ label: t(`${F}.structureBelow.label`), value: yesNo(e.structureBelow, t) })
    if (e.structureBelow) {
      rows.push({ label: labelled(t(`${F}.structureGap.label`), 'H_GB'), value: quantity(e.structureGap, 'mm', f) })
    }
  } else if (e.device === 'multiBeam') {
    const heights = e.beamHeights.map((h) => f.number(h, 1)).join('; ')
    rows.push(
      { label: t(`${F}.beamHeights.label`), value: heights ? `${heights} mm` : REPORT_EMPTY },
      { label: labelled(t(`${F}.hazardHeight.label`), 'H_H'), value: quantity(e.hazardHeight, 'mm', f) },
    )
    if (!e.stepArrangement) {
      rows.push({ label: labelled(t(`${F}.openingHeight.label`), 'h'), value: quantity(e.openingHeight, 'mm', f) })
    }
    rows.push({ label: t(`${F}.stepArrangement.label`), value: yesNo(e.stepArrangement, t) })
    if (e.stepArrangement) {
      rows.push({ label: labelled(t(`${F}.stepHeight.label`), 'H_S'), value: quantity(e.stepHeight, 'mm', f) })
    }
    rows.push(environment)
  }
  return rows
}

function guardRows(inputs: SafetyDistanceInputs, f: SafetyDistanceFormat): KeyValue[] {
  const { t } = f
  const g = inputs.guard
  const rows: KeyValue[] = [{ label: t(`${F}.locking.label`), value: yesNo(g.locking, t) }]
  if (g.locking) rows.push({ label: labelled(t(`${F}.unlockDelay.label`), 't_DY'), value: quantity(g.unlockDelay, 's', f) })
  rows.push({ label: t(`${F}.openingMethod.label`), value: t(`${F}.openingMethod.${g.openingMethod}`) })
  if (g.openingMethod === 'direct') {
    rows.push(
      { label: t(`${F}.shape.label`), value: t(`${F}.shape.${g.openingShape}`) },
      { label: labelled(t(`${F}.opening.label`), 'e'), value: quantity(g.opening, 'mm', f) },
    )
    if (g.openingShape === 'slot') rows.push({ label: t(`${F}.slotLength.label`), value: quantity(g.slotLength, 'mm', f) })
  } else {
    rows.push(
      { label: labelled(t(`${F}.guardWidth.label`), 'G_W'), value: quantity(g.guardWidth, 'mm', f) },
      { label: labelled(t(`${F}.angle.label`), 'ω'), value: quantity(g.angle, '°', f) },
      { label: labelled(t(`${F}.guardThickness.label`), 'G_T'), value: quantity(g.guardThickness, 'mm', f) },
    )
  }
  rows.push({ label: t(`${F}.reachThroughOwn.label`), value: yesNo(g.reachThroughOwn, t) })
  if (g.reachThroughOwn) {
    rows.push({ label: labelled(t(`${F}.reachThrough.label`), 'D_GT'), value: quantity(g.reachThrough, 'mm', f) })
  }
  return rows
}

export function inputRows(inputs: SafetyDistanceInputs, f: SafetyDistanceFormat): KeyValue[] {
  const { t } = f
  let rows: KeyValue[]
  switch (inputs.mode) {
    case 'espe':
      rows = espeRows(inputs, f)
      break
    case 'parallel': {
      const p = inputs.parallel
      rows = [
        { label: labelled(t(`${F}.detection.label`), 'd_e'), value: quantity(p.detection, 'mm', f) },
        { label: labelled(t(`${F}.fieldHeight.label`), 'H_D'), value: quantity(p.fieldHeight, 'mm', f) },
        { label: labelled(t(`${F}.fieldDepth.label`), 'F_D'), value: quantity(p.fieldDepth, 'mm', f) },
        { label: labelled(t(`${F}.obstacleGap.label`), 'G_D'), value: quantity(p.obstacleGap, 'mm', f) },
        { label: t(`${F}.standingDetected.label`), value: yesNo(p.standingDetected, t) },
      ]
      break
    }
    case 'twoHand': {
      const h = inputs.twoHand
      rows = [
        { label: t(`${F}.encroachmentPrevented.label`), value: yesNo(h.encroachmentPrevented, t) },
        {
          label: t(`${F}.twoHandType.label`),
          value: h.type === null ? t(`${F}.twoHandType.placeholder`) : t(`${F}.twoHandType.${h.type}`),
        },
        { label: t(`${F}.actuatorGap.label`), value: quantity(h.actuatorGap, 'mm', f) },
      ]
      break
    }
    case 'holdToRun':
      rows = [{ label: t(`${F}.actuation.label`), value: t(`${F}.actuation.${inputs.holdToRun.actuation}`) }]
      break
    case 'guard':
      rows = guardRows(inputs, f)
      break
    case 'structure': {
      const s = inputs.structure
      rows = [
        { label: labelled(t(`${F}.structureHazardHeight.label`), 'h_h'), value: quantity(s.hazardHeight, 'mm', f) },
        { label: labelled(t(`${F}.structureHeight.label`), 'h_ps'), value: quantity(s.structureHeight, 'mm', f) },
        { label: labelled(t(`${F}.structureDistance.label`), 's_h'), value: quantity(s.distance, 'mm', f) },
        { label: t(`${F}.lowRisk.label`), value: yesNo(s.lowRisk, t) },
      ]
      break
    }
    case 'opening': {
      const o = inputs.opening
      rows = [
        { label: t(`${F}.shape.label`), value: t(`${F}.shape.${o.shape}`) },
        { label: t(`${F}.limb.label`), value: t(`${F}.limb.${o.limb}`) },
        { label: labelled(t(`${F}.openingSize.label`), 'e'), value: quantity(o.size, 'mm', f) },
      ]
      if (o.shape === 'slot') rows.push({ label: t(`${F}.slotLength.label`), value: quantity(o.slotLength, 'mm', f) })
      rows.push({ label: labelled(t(`${F}.openingDistance.label`), 's_r'), value: quantity(o.distance, 'mm', f) })
      if (o.limb === 'upper') rows.push({ label: t(`${F}.children.label`), value: yesNo(o.children, t) })
      break
    }
    case 'crushing': {
      const c = inputs.crushing
      rows = [
        {
          label: t(`${F}.bodyPart.label`),
          value: c.bodyPart === null ? t(`${F}.bodyPart.placeholder`) : t(`${F}.bodyPart.${c.bodyPart}`),
        },
        { label: labelled(t(`${F}.crushingGap.label`), 'a'), value: quantity(c.gap, 'mm', f) },
      ]
      break
    }
  }
  if (usesSupplement(inputs)) {
    rows.push({ label: labelled(t(`${F}.supplement.label`), 'Z'), value: formatQuantity(inputs.supplement ?? 0, 'mm', f) })
  }
  return rows
}

const COMPONENT_SYMBOLS: Record<(typeof RESPONSE_TIME_COMPONENTS)[number], string> = {
  tI: 't_I',
  tL: 't_L',
  tO: 't_O',
  tD: 't_D',
  tR: 't_R',
  tM: 't_M',
  tF: 't_F',
  tS: 't_S',
}

export function responseTimeSection(inputs: SafetyDistanceInputs, result: SafetyDistanceResult, f: SafetyDistanceFormat): Content {
  const { t } = f
  const rt = inputs.responseTime
  const rows: KeyValue[] = [{ label: t(`${RT}.method`), value: t(`${RT}.methods.${rt.method}`) }]
  const content: Content[] = []
  if (rt.method === 'direct') {
    rows.push({ label: labelled(t(`${RT}.direct.label`), 'T'), value: quantity(rt.direct, 's', f) })
  } else if (rt.method === 'components') {
    for (const component of RESPONSE_TIME_COMPONENTS) {
      rows.push({ label: labelled(t(`${RT}.components.${component}`), COMPONENT_SYMBOLS[component]), value: quantity(rt[component], 's', f) })
    }
  } else {
    const list = (values: number[]) => (values.length === 0 ? REPORT_EMPTY : `${values.map((v) => f.number(v, 4)).join('; ')} s`)
    rows.push(
      { label: t(`${RT}.conditions.cold`), value: list(rt.cold) },
      { label: t(`${RT}.conditions.warm`), value: list(rt.warm) },
      { label: labelled(t(`${RT}.tolerance.label`), 't_F'), value: quantity(rt.tF, 's', f) },
    )
  }
  content.push(keyValueGrid(rows, 1))
  const stats = result.responseTime.conditions
  if (stats.length > 0) {
    const seconds = (value: number | null) => (value === null ? REPORT_EMPTY : formatQuantity(value, 's', f))
    content.push(
      keepTogether([
        subheading(t(`${RT}.statsTitle`)),
        dataTable(
        [
          { header: t(`${RT}.stats.condition`), width: '*' },
          { header: 'n', align: 'right' },
          { header: rich('x_max'), align: 'right' },
          { header: rich('x̄'), align: 'right' },
          { header: rich('s_x'), align: 'right' },
          { header: rich('x̄ + 3 · s_x'), align: 'right' },
          { header: 'T', align: 'right' },
        ],
        stats.map((c) => [
          t(`${RT}.conditions.${c.condition}`),
          String(c.n),
          seconds(c.max),
          seconds(c.mean),
          seconds(c.sd),
          seconds(c.meanPlus3Sd),
          cell(seconds(c.t), { style: 'emphasis' }),
        ]),
      ),
        footnote(rich(t(`${RT}.statsFormula`))),
      ]),
    )
  }
  return section(t(`${P}.sections.responseTime`), ...content)
}

/** The inputs of the chosen mode. */
export function inputsSection(inputs: SafetyDistanceInputs, f: SafetyDistanceFormat): Content {
  return section(f.t(`${P}.sections.inputs.${inputs.mode}`), keyValueGrid(inputRows(inputs, f), 1))
}
