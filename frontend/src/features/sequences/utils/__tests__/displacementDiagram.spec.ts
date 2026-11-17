import { describe, expect, it } from 'vitest'

import type { SequenceDeviceName } from '../../composables/useSequenceNames'
import type { SequenceStep } from '../../types/sequence'
import { buildDisplacementDiagram } from '../displacementDiagram'
import { normalizeSteps } from '../steps'

const lift: SequenceDeviceName = {
  id: 5,
  name: 'B01 Lift P1',
  nameAscii: 'B01_Lift_P1',
  kind: 'Linear drive',
  archived: false,
  initialPositionId: 10,
  initialPositionValue: null,
  drivenById: null,
  positionMap: {},
  positions: [
    { id: 10, label: 'Retracted', unit: null, takesValue: false, archived: false, travelTimeMs: null },
    { id: 11, label: 'Extended', unit: null, takesValue: false, archived: false, travelTimeMs: null },
    { id: 12, label: 'Stroke', unit: 'mm', takesValue: true, archived: false, travelTimeMs: null },
  ],
}
const vacuum: SequenceDeviceName = {
  ...lift,
  id: 6,
  name: 'B01 Vacuum P1',
  initialPositionId: null,
  positions: [
    { id: 20, label: 'Off', unit: null, takesValue: false, archived: false, travelTimeMs: null },
    { id: 21, label: 'On', unit: null, takesValue: false, archived: false, travelTimeMs: null },
  ],
}
const devices = new Map([
  [5, lift],
  [6, vacuum],
])

const STEPS: SequenceStep[] = normalizeSteps([
  {
    key: 's1',
    actions: [
      {
        key: 'a1',
        kind: 'device',
        qualifier: 'stored',
        device_id: 5,
        position_id: 12,
        value: { common: 50, per_variant: { '2': 80 } },
      },
    ],
    transitions: [{ key: 't1', target: 'next' }],
  },
  {
    key: 's2',
    actions: [
      { key: 'a2', kind: 'device', qualifier: 'continuous', device_id: 6, position_id: 21 },
      { key: 'a3', kind: 'text', qualifier: 'pulse', text: 'Count part' },
    ],
    transitions: [{ key: 't2', target: 'next' }],
  },
  {
    key: 's3',
    timeout_ms: 2000,
    actions: [{ key: 'a4', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 10 }],
    transitions: [{ key: 't3', target: 's1' }],
  },
])

describe('buildDisplacementDiagram', () => {
  it('follows each device from its initial position through the steps', () => {
    const diagram = buildDisplacementDiagram(STEPS, devices, null)
    expect(diagram.rows.map((row) => row.name)).toEqual(['B01 Lift P1', 'B01 Vacuum P1'])
    const [liftRow, vacuumRow] = diagram.rows
    expect(liftRow!.segments.map((s) => [s.from, s.to, s.shape])).toEqual([
      [0, 0, 'hold'],
      [0, 2, 'move'],
      [2, 2, 'hold'],
      [2, 0, 'move'],
    ])
    expect(liftRow!.segments[1]!.value).toBe('50 mm')
    // A continuous action ends with its step, and an unset initial position stays unknown.
    expect(vacuumRow!.segments.map((s) => [s.from, s.to, s.shape])).toEqual([
      [null, null, 'hold'],
      [null, null, 'hold'],
      [null, 1, 'continuous'],
      [null, null, 'hold'],
    ])
  })

  it("shows a variant's own value and where the steps lead elsewhere", () => {
    const diagram = buildDisplacementDiagram(STEPS, devices, 2)
    expect(diagram.rows[0]!.segments[1]!.value).toBe('80 mm')
    expect(diagram.columns.map((c) => c.jumps)).toEqual([[], [], [], ['→ 1']])
    expect(diagram.columns[2]!.texts).toEqual(['Count part'])
    expect(diagram.columns[3]!.timeoutMs).toBe(2000)
  })

  it('adds a row for a driven device that follows its driver', () => {
    const follower: SequenceDeviceName = { ...lift, id: 7, name: 'B01 Lift P2', drivenById: 5 }
    const withFollower = new Map([...devices, [7, follower]])
    const diagram = buildDisplacementDiagram(STEPS, withFollower, null)
    expect(diagram.rows.map((row) => [row.name, row.drivenBy])).toEqual([
      ['B01 Lift P1', null],
      ['B01 Lift P2', 'B01 Lift P1'],
      ['B01 Vacuum P1', null],
    ])
    const [driverRow, followerRow] = diagram.rows
    expect(followerRow!.segments.map((s) => [s.from, s.to])).toEqual(driverRow!.segments.map((s) => [s.from, s.to]))
    expect(followerRow!.segments[1]!.value).toBeNull()
  })
})
