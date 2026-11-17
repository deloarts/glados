import { describe, expect, it } from 'vitest'

import type { SequenceStep } from '../../types/sequence'
import { normalizeSteps } from '../steps'
import { stepProblems } from '../validation'

const context = {
  takesValue: (_deviceId: number, positionId: number) => positionId === 11,
  liveVariantIds: [1, 2],
  isDriven: (deviceId: number) => deviceId === 6,
}

function steps(raw: SequenceStep[]): SequenceStep[] {
  return normalizeSteps(raw)
}

describe('stepProblems', () => {
  it('accepts a cycle with values per variant', () => {
    const result = stepProblems(
      steps([
        {
          key: 's1',
          actions: [
            {
              key: 'a1',
              kind: 'device',
              qualifier: 'stored',
              device_id: 5,
              position_id: 11,
              value: { per_variant: { '1': 60, '2': 80 } },
            },
          ],
          transitions: [{ key: 't1', target: 'next' }],
        },
        { key: 's2', transitions: [{ key: 't2', target: 's1' }] },
      ]),
      context,
    )
    expect(result.size).toBe(0)
  })

  it('points out a missing variant value, a last step without next and unconditioned branches', () => {
    const result = stepProblems(
      steps([
        {
          key: 's1',
          actions: [
            { key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11, value: { per_variant: { '1': 60 } } },
          ],
          transitions: [
            { key: 't1', target: 'next' },
            { key: 't2', target: 'end' },
          ],
        },
      ]),
      context,
    )
    expect(result.get('s1')?.errors).toEqual(['valueMissing', 'noNextStep', 'branchWithoutCondition'])
  })

  it('warns when two branches have the same condition', () => {
    const condition = [{ kind: 'external' as const, text: 'Start' }]
    const result = stepProblems(
      steps([
        {
          key: 's1',
          transitions: [
            { key: 't1', target: 'end', condition },
            { key: 't2', target: 's1', condition },
          ],
        },
      ]),
      context,
    )
    expect(result.get('s1')).toEqual({ errors: [], warnings: ['branchOverlap'] })
  })

  it('warns when a transition waits for a moved device in another position', () => {
    const result = stepProblems(
      steps([
        {
          key: 's1',
          actions: [{ key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 10 }],
          transitions: [
            { key: 't1', target: 'end', condition: [{ kind: 'device_position', device_id: 5, position_id: 12 }] },
          ],
        },
      ]),
      context,
    )
    expect(result.get('s1')).toEqual({ errors: [], warnings: ['conditionContradicts'] })
  })

  it('accepts a transition that waits for the position the step moves to', () => {
    const result = stepProblems(
      steps([
        {
          key: 's1',
          actions: [{ key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 10 }],
          transitions: [
            { key: 't1', target: 'end', condition: [{ kind: 'device_position', device_id: 5, position_id: 10 }] },
          ],
        },
      ]),
      context,
    )
    expect(result.size).toBe(0)
  })
})
