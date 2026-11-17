import { describe, expect, it } from 'vitest'

import type { SequenceStep } from '../../types/sequence'
import { newKey, normalizeSteps, sameSteps } from '../steps'

const SAVED: SequenceStep[] = [
  {
    key: 's1',
    description: null,
    timeout_ms: null,
    expected_duration_ms: null,
    actions: [
      {
        key: 'a1',
        kind: 'device',
        qualifier: 'stored',
        device_id: 5,
        position_id: 11,
        value: { common: null, per_variant: { '1': 60, '2': 80 } },
        text: null,
        description: null,
        condition: [],
        duration_ms: null,
      },
    ],
    transitions: [{ key: 't1', target: 'next', condition: [] }],
  },
]

describe('steps', () => {
  it('fills the defaults so an edited step compares equal to the saved one', () => {
    // As an editor might build it, with the defaults left out.
    const edited: SequenceStep[] = [
      {
        key: 's1',
        actions: [
          {
            key: 'a1',
            kind: 'device',
            qualifier: 'stored',
            device_id: 5,
            position_id: 11,
            value: { per_variant: { '2': 80, '1': 60 } },
          },
        ],
        transitions: [{ key: 't1', target: 'next' }],
      },
    ]
    expect(normalizeSteps(edited)).toEqual(SAVED)
    expect(sameSteps(SAVED, edited)).toBe(true)
  })

  it('tells a changed value apart', () => {
    const changed = normalizeSteps(SAVED)
    changed[0]!.actions![0]!.value = { common: 70, per_variant: {} }
    expect(sameSteps(SAVED, changed)).toBe(false)
  })

  it('makes keys the server accepts', () => {
    const keys = new Set(Array.from({ length: 50 }, () => newKey('s')))
    expect(keys.size).toBe(50)
    for (const key of keys) expect(key).toMatch(/^[A-Za-z0-9_-]{1,40}$/)
  })
})
