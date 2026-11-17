import { describe, expect, it } from 'vitest'

import type { SequenceDeviceName } from '../../composables/useSequenceNames'
import type { SequenceConditionTerm, SequenceStep } from '../../types/sequence'
import { normalizeSteps } from '../steps'
import { estimateCycle, estimateStep, estimateSteps } from '../timing'

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
    { id: 10, label: 'Retracted', unit: null, takesValue: false, archived: false, travelTimeMs: 300 },
    { id: 11, label: 'Extended', unit: null, takesValue: false, archived: false, travelTimeMs: 500 },
    { id: 12, label: 'Middle', unit: null, takesValue: false, archived: false, travelTimeMs: null },
  ],
}
const devices = new Map([[5, lift]])

const move = (key: string, positionId: number, extra: object = {}) => ({
  key,
  kind: 'device' as const,
  qualifier: 'stored' as const,
  device_id: 5,
  position_id: positionId,
  ...extra,
})
const external: SequenceConditionTerm = { kind: 'external', text: 'Robot ready' }
const wait = (ms: number): SequenceConditionTerm => ({ kind: 'time', duration_ms: { common: ms, per_variant: {} } })

function only(step: Partial<SequenceStep>): SequenceStep {
  return normalizeSteps([{ key: 's1', transitions: [{ key: 't1', target: 'end' }], ...step }])[0] as SequenceStep
}

describe('estimateStep', () => {
  it('takes the longest action, with the delay of its time condition', () => {
    const step = only({ actions: [move('a1', 10), move('a2', 11, { condition: [wait(400)] })] })
    expect(estimateStep(step, step.transitions?.[0], devices, null)).toEqual({ ms: 900, estimated: true })
  })

  it('prefers the action time per variant over the travel time', () => {
    const step = only({ actions: [move('a1', 11, { duration_ms: { common: 200, per_variant: { '2': 700 } } })] })
    expect(estimateStep(step, undefined, devices, 1).ms).toBe(200)
    expect(estimateStep(step, undefined, devices, 2).ms).toBe(700)
  })

  it('is unestimated for an action without time or an external wait, unless the step has an expected duration', () => {
    const noTime = only({ actions: [move('a1', 12)] })
    expect(estimateStep(noTime, undefined, devices, null).estimated).toBe(false)
    const waiting = only({ transitions: [{ key: 't1', target: 'end', condition: [external] }] })
    expect(estimateStep(waiting, waiting.transitions?.[0], devices, null)).toEqual({ ms: 0, estimated: false })
    const expected = only({
      expected_duration_ms: { common: 2000, per_variant: {} },
      transitions: [{ key: 't1', target: 'end', condition: [external] }],
    })
    expect(estimateStep(expected, expected.transitions?.[0], devices, null)).toEqual({ ms: 2000, estimated: true })
  })

  it('counts a pulse without time as instant', () => {
    const step = only({ actions: [{ key: 'a1', kind: 'text', qualifier: 'pulse', text: 'Reset counter' }] })
    expect(estimateStep(step, undefined, devices, null)).toEqual({ ms: 0, estimated: true })
  })
})

describe('estimateCycle', () => {
  // Step 2 checks the part: OK goes on to step 3, not OK repeats step 1's
  // move through step 4 and then ends.
  const STEPS = normalizeSteps([
    { key: 's1', actions: [move('a1', 11)], transitions: [{ key: 't1', target: 'next' }] },
    {
      key: 's2',
      actions: [move('a2', 10)],
      transitions: [
        { key: 'ok', target: 's3', condition: [wait(100)] },
        { key: 'nok', target: 's4', condition: [wait(100)] },
      ],
    },
    { key: 's3', actions: [move('a3', 11)], transitions: [{ key: 't3', target: 's1' }] },
    {
      key: 's4',
      expected_duration_ms: { common: 5000, per_variant: {} },
      transitions: [
        { key: 'again', target: 's2', condition: [external] },
        { key: 'stop', target: 'end', condition: [external] },
      ],
    },
  ])

  it('follows the first branch by default and returns to step 1', () => {
    const cycle = estimateCycle(STEPS, devices, null)
    expect(cycle?.picked).toEqual({ ms: 500 + 300 + 500, unestimated: 0, stepKeys: ['s1', 's2', 's3'] })
  })

  it('follows a picked branch and counts the loop back once', () => {
    const cycle = estimateCycle(STEPS, devices, null, { s2: 'nok' })
    // Step 4 cannot go back to step 2, which the pass has been through, so it stops.
    expect(cycle?.picked.stepKeys).toEqual(['s1', 's2', 's4'])
    expect(cycle?.picked.ms).toBe(500 + 300 + 5000)
  })

  it('finds the worst case over all branches', () => {
    const cycle = estimateCycle(STEPS, devices, null)
    expect(cycle?.worst.stepKeys).toEqual(['s1', 's2', 's4'])
    expect(cycle?.worst.ms).toBe(5800)
  })

  it('counts the unestimated steps of a pass', () => {
    const steps = normalizeSteps([
      { key: 's1', actions: [move('a1', 12)], transitions: [{ key: 't1', target: 'next' }] },
      { key: 's2', actions: [move('a2', 10)], transitions: [{ key: 't2', target: 'end' }] },
    ])
    expect(estimateCycle(steps, devices, null)?.picked).toEqual({ ms: 300, unestimated: 1, stepKeys: ['s1', 's2'] })
    expect(estimateSteps(steps, devices, null).get('s1')).toEqual({ ms: 0, estimated: false })
  })

  it('has nothing to estimate without steps', () => {
    expect(estimateCycle([], devices, null)).toBeNull()
  })
})
