import type { SequenceDeviceName } from '../composables/useSequenceNames'
import type { SequenceStep, SequenceVariantValue } from '../types/sequence'
import { stateName } from './positionNames'
import { TARGET_END, TARGET_NEXT } from '../types/sequence'

/**
 * The model of a displacement-step diagram (formerly VDI 3260, now part of
 * the GRAFCET family of charts): one row per device the steps move, one
 * column per step after a start column, and in each column where the
 * device is from start to end, and a row for each device driven by one of
 * them, following its driver. The positions of a device's kind are its
 * levels, the first one at the bottom, so a cylinder's retracted position
 * lies below its extended one. Steps are drawn in their order; where a
 * step leads elsewhere than the next one, the column says where.
 */

export interface DiagramLevel {
  positionId: number
  label: string
}

/** Where the device is during one column; levels index DiagramRow.levels. */
export interface DiagramSegment {
  /** At the column's start; null where unknown, such as a device without an initial position. */
  from: number | null
  /** At the column's end. */
  to: number | null
  /** A continuous action holds the target only while its step is active, a pulse touches it once. */
  shape: 'hold' | 'move' | 'continuous' | 'pulse'
  /** The value at the target, for positions that take one. */
  value: string | null
}

export interface DiagramRow {
  deviceId: number
  name: string
  kind: string
  levels: DiagramLevel[]
  /** Column 0 is the start state, column i the step numbered i. */
  segments: DiagramSegment[]
  /** The driver's name for a device that only follows it. */
  drivenBy: string | null
}

export interface DiagramColumn {
  /** 0 for the start state. */
  number: number
  label: string
  /** Text actions of the step, which have no row of their own. */
  texts: string[]
  /** Where the step goes when it leads elsewhere than the next one, such as "→ 1" or "end". */
  jumps: string[]
  timeoutMs: number | null
}

export interface DisplacementDiagram {
  columns: DiagramColumn[]
  rows: DiagramRow[]
}

function valueFor(value: SequenceVariantValue | null | undefined, variantId: number | null): number | null {
  if (!value) return null
  if (variantId !== null) {
    const own = value.per_variant?.[String(variantId)]
    if (own !== undefined) return own
  }
  return value.common ?? null
}

function formatValue(value: number | null, unit: string | null): string | null {
  if (value === null) return null
  return unit ? `${value} ${unit}` : String(value)
}

/**
 * Builds the diagram for one variant (null for the common values). `devices`
 * are the names the sequence shows; only devices one of its steps moves get
 * a row, in the order the steps first move them.
 */
export function buildDisplacementDiagram(
  steps: readonly SequenceStep[],
  devices: ReadonlyMap<number, SequenceDeviceName>,
  variantId: number | null,
): DisplacementDiagram {
  const order: number[] = []
  for (const step of steps) {
    for (const action of step.actions ?? []) {
      if (action.kind === 'device' && action.device_id != null && !order.includes(action.device_id)) {
        order.push(action.device_id)
      }
    }
  }

  const stepNumbers = new Map(steps.map((step, index) => [step.key, index + 1]))
  const columns: DiagramColumn[] = [{ number: 0, label: '0', texts: [], jumps: [], timeoutMs: null }]
  steps.forEach((step, index) => {
    const jumps: string[] = []
    for (const transition of step.transitions ?? []) {
      const target = transition.target ?? TARGET_NEXT
      if (target === TARGET_END) jumps.push('end')
      else if (target !== TARGET_NEXT && stepNumbers.get(target) !== index + 2) jumps.push(`→ ${stepNumbers.get(target) ?? '?'}`)
    }
    columns.push({
      number: index + 1,
      label: String(index + 1),
      texts: (step.actions ?? []).filter((a) => a.kind === 'text' && a.text).map((a) => a.text!),
      jumps,
      timeoutMs: step.timeout_ms ?? null,
    })
  })

  const rows: DiagramRow[] = []
  for (const deviceId of order) {
    const device = devices.get(deviceId)
    if (!device) continue
    const timeline = positionTimeline(steps, device, variantId)
    rows.push(toRow(device, timeline, steps))
    // A device driven by this one follows it, through the position map for
    // a driver of another kind.
    for (const follower of devices.values()) {
      if (follower.drivenById !== deviceId || order.includes(follower.id)) continue
      const followed = timeline.map((segment, column) => ({
        ...segment,
        from: column === 0 ? follower.initialPositionId : follow(follower, segment.from),
        to: column === 0 ? follower.initialPositionId : follow(follower, segment.to),
        value: null,
      }))
      rows.push({ ...toRow(follower, followed, steps), drivenBy: device.name })
    }
  }
  return { columns, rows }
}

/** Where a device is in each column, by position id; column 0 is the start state. */
interface PositionSegment {
  from: number | null
  to: number | null
  shape: DiagramSegment['shape']
  value: string | null
}

function positionTimeline(
  steps: readonly SequenceStep[],
  device: SequenceDeviceName,
  variantId: number | null,
): PositionSegment[] {
  const unitOf = (positionId: number | null | undefined) =>
    device.positions.find((p) => p.id === positionId)?.unit ?? null
  let current = device.initialPositionId
  const timeline: PositionSegment[] = [
    {
      from: current,
      to: current,
      shape: 'hold',
      value: formatValue(device.initialPositionValue, unitOf(device.initialPositionId)),
    },
  ]
  for (const step of steps) {
    const action = (step.actions ?? []).find((a) => a.kind === 'device' && a.device_id === device.id)
    if (!action) {
      timeline.push({ from: current, to: current, shape: 'hold', value: null })
      continue
    }
    const target = action.position_id ?? null
    const value = formatValue(valueFor(action.value, variantId), unitOf(action.position_id))
    const qualifier = action.qualifier ?? 'stored'
    if (qualifier === 'stored') {
      timeline.push({ from: current, to: target, shape: current === target ? 'hold' : 'move', value })
      current = target
    } else {
      // Continuous and pulse actions leave the device where it was once the step is over.
      timeline.push({ from: current, to: target, shape: qualifier, value })
    }
  }
  return timeline
}

/** The follower's position for a driver position: the same id for the same kind, else the map. */
function follow(follower: SequenceDeviceName, driverPosition: number | null): number | null {
  if (driverPosition === null) return null
  if (Object.keys(follower.positionMap).length === 0) {
    return follower.positions.some((p) => p.id === driverPosition) ? driverPosition : null
  }
  const own = follower.positionMap[String(driverPosition)]
  return own === undefined ? null : Number(own)
}

function toRow(device: SequenceDeviceName, timeline: PositionSegment[], steps: readonly SequenceStep[]): DiagramRow {
  const levels = device.positions
    .filter((p) => !p.archived || steps.some((s) => (s.actions ?? []).some((a) => a.position_id === p.id)))
    .map((p) => ({ positionId: p.id, label: stateName(p) }))
  const levelOf = (positionId: number | null) => {
    if (positionId === null) return null
    const index = levels.findIndex((level) => level.positionId === positionId)
    return index === -1 ? null : index
  }
  return {
    deviceId: device.id,
    name: device.name,
    kind: device.kind,
    levels,
    segments: timeline.map((segment) => ({
      from: levelOf(segment.from),
      to: levelOf(segment.to),
      shape: segment.shape,
      value: segment.value,
    })),
    drivenBy: null,
  }
}
