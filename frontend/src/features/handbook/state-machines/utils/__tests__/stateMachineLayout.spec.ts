import { describe, it, expect } from 'vitest'

import { layoutStateMachine } from '../stateMachineLayout'

describe('layoutStateMachine', () => {
  it('layers states by BFS depth from the initial state', () => {
    const layout = layoutStateMachine(
      [
        { value: 'queued', initial: true, terminal: false },
        { value: 'in_progress', initial: false, terminal: false },
        { value: 'paused', initial: false, terminal: false },
        { value: 'completed', initial: false, terminal: true },
      ],
      [
        { from_state: 'queued', to_state: 'in_progress' },
        { from_state: 'in_progress', to_state: 'paused' },
        { from_state: 'paused', to_state: 'in_progress' },
        { from_state: 'in_progress', to_state: 'completed' },
      ],
    )

    expect(layout.layerOf.queued).toBe(0)
    expect(layout.layerOf.in_progress).toBe(1)
    expect(layout.layerOf.paused).toBe(2)
    // Terminal states are pulled into the single last layer even though
    // 'completed' is only one hop from 'in_progress' (depth 2), same as
    // 'paused': both would otherwise tie, but only 'completed' is terminal.
    expect(layout.layerOf.completed).toBe(2)
    expect(layout.layers).toEqual([['queued'], ['in_progress'], ['paused', 'completed']])
  })

  it('is deterministic across repeated calls with the same input', () => {
    const states = [
      { value: 'a', initial: true, terminal: false },
      { value: 'b', initial: false, terminal: false },
      { value: 'c', initial: false, terminal: true },
    ]
    const edges = [
      { from_state: 'a', to_state: 'b' },
      { from_state: 'b', to_state: 'c' },
    ]

    const first = layoutStateMachine(states, edges)
    const second = layoutStateMachine(states, edges)

    expect(second).toEqual(first)
  })

  it('handles a cycle without infinite looping and covers every state', () => {
    const layout = layoutStateMachine(
      [
        { value: 'a', initial: true, terminal: false },
        { value: 'b', initial: false, terminal: false },
      ],
      [
        { from_state: 'a', to_state: 'b' },
        { from_state: 'b', to_state: 'a' },
      ],
    )

    expect(layout.layerOf).toEqual({ a: 0, b: 1 })
    expect(layout.layers).toEqual([['a'], ['b']])
  })

  it('handles a self-loop edge without infinite looping', () => {
    const layout = layoutStateMachine(
      [{ value: 'a', initial: true, terminal: false }],
      [{ from_state: 'a', to_state: 'a' }],
    )

    expect(layout.layerOf).toEqual({ a: 0 })
    expect(layout.layers).toEqual([['a']])
  })

  it('falls back to the first state as the BFS root when none is marked initial', () => {
    const layout = layoutStateMachine(
      [
        { value: 'first', initial: null, terminal: false },
        { value: 'second', initial: null, terminal: false },
      ],
      [{ from_state: 'first', to_state: 'second' }],
    )

    expect(layout.layerOf).toEqual({ first: 0, second: 1 })
  })

  it('gives a disconnected state its own deterministic layer instead of dropping it', () => {
    const layout = layoutStateMachine(
      [
        { value: 'a', initial: true, terminal: false },
        { value: 'b', initial: false, terminal: false },
        { value: 'unreachable', initial: false, terminal: false },
      ],
      [{ from_state: 'a', to_state: 'b' }],
    )

    expect(layout.layerOf.a).toBe(0)
    expect(layout.layerOf.b).toBe(1)
    expect(layout.layerOf.unreachable).toBe(2)
    expect(layout.layers.flat().sort()).toEqual(['a', 'b', 'unreachable'])
  })

  it('returns empty layout for no states', () => {
    expect(layoutStateMachine([], [])).toEqual({ layers: [], layerOf: {} })
  })

  it('lays out a fully cyclical machine with no terminal state at all (e.g. lot_position_kind)', () => {
    // Mirrors LotPositionKind: unassigned <-> external/internal <-> mixed,
    // every state has at least one outgoing transition, so none is terminal
    // and the "pull terminal states into the last layer" step never fires.
    const layout = layoutStateMachine(
      [
        { value: 'unassigned', initial: true, terminal: false },
        { value: 'external', initial: false, terminal: false },
        { value: 'internal', initial: false, terminal: false },
        { value: 'mixed', initial: false, terminal: false },
      ],
      [
        { from_state: 'unassigned', to_state: 'external' },
        { from_state: 'unassigned', to_state: 'internal' },
        { from_state: 'external', to_state: 'unassigned' },
        { from_state: 'external', to_state: 'mixed' },
        { from_state: 'internal', to_state: 'unassigned' },
        { from_state: 'internal', to_state: 'mixed' },
        { from_state: 'mixed', to_state: 'external' },
        { from_state: 'mixed', to_state: 'internal' },
        { from_state: 'mixed', to_state: 'unassigned' },
      ],
    )

    // No crash, every state still lands in a deterministic layer purely from
    // BFS depth. Nothing is forced into a "last" layer just because the
    // machine happens to have no terminal state to pull there.
    expect(layout.layerOf).toEqual({
      unassigned: 0,
      external: 1,
      internal: 1,
      mixed: 2,
    })
    expect(layout.layers).toEqual([['unassigned'], ['external', 'internal'], ['mixed']])
  })
})
