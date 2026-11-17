import { describe, expect, it } from 'vitest'

import type { SequenceStep } from '../../types/sequence'
import { normalizeSteps } from '../steps'
import { arrivalSuggestions } from '../suggestions'

function step(raw: SequenceStep): SequenceStep {
  return normalizeSteps([raw])[0]!
}

describe('arrivalSuggestions', () => {
  it('offers the position each moved device goes to, once, and leaves out pulses and text', () => {
    const result = arrivalSuggestions(
      step({
        key: 's1',
        actions: [
          { key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 },
          { key: 'a2', kind: 'device', qualifier: 'continuous', device_id: 6, position_id: 21 },
          { key: 'a3', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 },
          { key: 'a4', kind: 'device', qualifier: 'pulse', device_id: 7, position_id: 31 },
          { key: 'a5', kind: 'text', qualifier: 'stored', text: 'Operator checks the part' },
          { key: 'a6', kind: 'device', qualifier: 'stored', device_id: 8, position_id: null },
        ],
        transitions: [{ key: 't1', target: 'next' }],
      }),
      [],
    )
    expect(result.map((term) => [term.kind, term.device_id, term.position_id])).toEqual([
      ['device_position', 5, 11],
      ['device_position', 6, 21],
    ])
  })

  it('leaves out what the condition already holds', () => {
    const result = arrivalSuggestions(
      step({
        key: 's1',
        actions: [
          { key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 },
          { key: 'a2', kind: 'device', qualifier: 'stored', device_id: 6, position_id: 21 },
        ],
        transitions: [{ key: 't1', target: 'next' }],
      }),
      [{ kind: 'device_position', device_id: 5, position_id: 11 }],
    )
    expect(result.map((term) => term.device_id)).toEqual([6])
  })
})
