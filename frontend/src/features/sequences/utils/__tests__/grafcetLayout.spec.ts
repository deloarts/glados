import { describe, expect, it } from 'vitest'

import type { SequenceStep } from '../../types/sequence'
import { GRAFCET, layoutGrafcet } from '../grafcetLayout'
import { normalizeSteps } from '../steps'

const text = {
  action: (action: { key: string }) => ({ device: null, text: `action ${action.key}` }),
  condition: (terms: readonly unknown[]) => (terms.length ? `${terms.length} terms` : ''),
}

const STEPS: SequenceStep[] = normalizeSteps([
  {
    key: 's1',
    actions: [{ key: 'a1', kind: 'text', qualifier: 'stored', text: 'Clamp' }],
    transitions: [{ key: 't1', target: 'next', condition: [{ kind: 'external', text: 'Start' }] }],
  },
  {
    key: 's2',
    timeout_ms: 2000,
    actions: [{ key: 'a2', kind: 'text', qualifier: 'pulse', text: 'Count', condition: [{ kind: 'external', text: 'Part' }] }],
    transitions: [
      { key: 't2', target: 'next', condition: [{ kind: 'external', text: 'Good' }] },
      { key: 't3', target: 's1', condition: [{ kind: 'external', text: 'Bad' }] },
    ],
  },
  { key: 's3', transitions: [{ key: 't4', target: 'end' }] },
])

describe('layoutGrafcet', () => {
  it('lays the steps out top down with the first as initial step', () => {
    const layout = layoutGrafcet(STEPS, text)
    expect(layout.steps.map((s) => [s.number, s.initial])).toEqual([
      [1, true],
      [2, false],
      [3, false],
    ])
    const ys = layout.steps.map((s) => s.y)
    expect(ys[0]!).toBeLessThan(ys[1]!)
    expect(ys[1]!).toBeLessThan(ys[2]!)
    expect(layout.steps[1]!.timeoutMs).toBe(2000)
  })

  it('writes the actions with their qualifier and condition', () => {
    const layout = layoutGrafcet(STEPS, text)
    expect(layout.actions.map((a) => [a.qualifier, a.text, a.condition])).toEqual([
      ['S', 'action a1', null],
      ['P', 'action a2', '1 terms'],
    ])
  })

  it('draws an alternative branch with a loop back and names where step 1 is entered from', () => {
    const layout = layoutGrafcet(STEPS, text)
    expect(layout.transitions.map((t) => t.label)).toEqual(['1 terms', '1 terms', '1 terms', '1'])
    const branchXs = layout.transitions.slice(1, 3).map((t) => t.x)
    expect(branchXs[1]!).toBeGreaterThan(branchXs[0]!)
    expect(layout.jumps.map((j) => j.target)).toEqual([1, null])
    expect(layout.steps[0]!.enteredFrom).toEqual([2])
  })

  it('writes each term of a condition on a line of its own and makes room for them', () => {
    const terms = (n: number) => Array.from({ length: n }, (_, i) => ({ kind: 'external' as const, text: `T${i}` }))
    const lines = { ...text, condition: (all: readonly { text?: string | null }[]) => all.map((term) => term.text).join(' · ') }
    const steps = (n: number) =>
      normalizeSteps([
        { key: 's1', transitions: [{ key: 't1', target: 'next', condition: terms(n) }] },
        { key: 's2', transitions: [{ key: 't2', target: 'end' }] },
      ])
    const one = layoutGrafcet(steps(1), lines)
    const three = layoutGrafcet(steps(3), lines)
    expect(three.transitions[0]!.lines).toEqual(['T0', 'T1', 'T2'])
    expect(three.transitions[0]!.label).toBe('T0 · T1 · T2')
    expect(three.steps[1]!.y - one.steps[1]!.y).toBe(28)
    expect(one.transitions[1]!.lines).toEqual(['1'])
  })

  it('widens the action boxes and the branches to their longest text', () => {
    const long = 'B01-W4-L Stanzzylinder Rundloch H1 Platine fixieren und stanzen, dann zurück'
    const plain = layoutGrafcet(STEPS, text)
    const wide = layoutGrafcet(STEPS, {
      action: () => ({ device: null, text: long }),
      condition: (terms) => (terms.length ? long : ''),
    })
    expect(plain.actionWidth).toBe(GRAFCET.actionWidth)
    expect(wide.actionWidth).toBeGreaterThan(28 + long.length * GRAFCET.charWidth)
    const branchXs = wide.transitions.slice(1, 3).map((t) => t.x)
    expect(branchXs[1]! - branchXs[0]!).toBeGreaterThan(20 + long.length * GRAFCET.charWidth)
    expect(wide.width).toBeGreaterThan(plain.width)
  })

  it('gives device actions a device cell as wide as the longest device name', () => {
    const steps = normalizeSteps([
      {
        key: 's1',
        actions: [
          { key: 'a1', kind: 'device', qualifier: 'stored', device_id: 1, position_id: 10 },
          { key: 'a2', kind: 'text', qualifier: 'stored', text: 'Close the guard' },
        ],
        transitions: [{ key: 't1', target: 'end' }],
      },
    ])
    const layout = layoutGrafcet(steps, {
      action: (action) =>
        action.kind === 'device' ? { device: 'B01-W4-L Punch cylinder', text: 'Extend' } : { device: null, text: action.text ?? '' },
      condition: () => '',
    })
    expect(layout.actions.map((a) => [a.device, a.text])).toEqual([
      ['B01-W4-L Punch cylinder', 'Extend'],
      [null, 'Close the guard'],
    ])
    expect(layout.deviceWidth).toBe(2 * GRAFCET.cellPadding + 'B01-W4-L Punch cylinder'.length * GRAFCET.charWidth)
    expect(layoutGrafcet(STEPS, text).deviceWidth).toBe(0)
  })
})
