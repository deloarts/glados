import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import { i18n } from '@/core/i18n'

import StateMachineDiagram from '../StateMachineDiagram.vue'
import type { StateMachineResponse } from '../../types/stateMachinesResponse'

// 'test_machine' is deliberately not in stateMachineLabels.ts's prefix map,
// so labels fall back to a humanized raw value, which keeps this test
// decoupled from that lookup table's contents.
function makeMachine(): StateMachineResponse {
  return {
    key: 'test_machine',
    entity: 'Test Entity',
    description: 'A tiny fixture machine with a back-edge.',
    kind: 'intent',
    rules: [],
    intents: [],
    transitions: [],
    states: [
      { value: 'queued', initial: true, terminal: false },
      { value: 'in_progress', initial: false, terminal: false },
      { value: 'paused', initial: false, terminal: false },
      { value: 'completed', initial: false, terminal: true },
    ],
    edges: [
      { from_state: 'queued', to_state: 'in_progress' },
      { from_state: 'in_progress', to_state: 'paused' },
      { from_state: 'paused', to_state: 'in_progress' },
      { from_state: 'in_progress', to_state: 'completed' },
    ],
  }
}

function mountDiagram(machine: StateMachineResponse) {
  return mount(StateMachineDiagram, {
    props: { machine },
    global: { plugins: [i18n] },
  })
}

describe('StateMachineDiagram', () => {
  it('renders one node per state, labeled with the humanized fallback', () => {
    const wrapper = mountDiagram(makeMachine())

    const nodes = wrapper.findAll('.sm-node')
    expect(nodes).toHaveLength(4)

    const labels = nodes.map((n) => n.find('.sm-node-label').text())
    expect(labels).toEqual(['Queued', 'In Progress', 'Paused', 'Completed'])
  })

  it('renders one edge path per edge', () => {
    const wrapper = mountDiagram(makeMachine())
    expect(wrapper.findAll('.sm-edge')).toHaveLength(4)
    // Every edge must produce an actual drawable path, not an empty 'd'.
    wrapper.findAll('.sm-edge').forEach((edge) => {
      expect(edge.attributes('d')).toBeTruthy()
    })
  })

  it('marks the initial state and no others', () => {
    const wrapper = mountDiagram(makeMachine())

    expect(wrapper.get('[data-state="queued"]').attributes('data-initial')).toBe('true')
    for (const value of ['in_progress', 'paused', 'completed']) {
      expect(wrapper.get(`[data-state="${value}"]`).attributes('data-initial')).toBe('false')
    }
  })

  it('marks the terminal state and no others', () => {
    const wrapper = mountDiagram(makeMachine())

    expect(wrapper.get('[data-state="completed"]').attributes('data-terminal')).toBe('true')
    for (const value of ['queued', 'in_progress', 'paused']) {
      expect(wrapper.get(`[data-state="${value}"]`).attributes('data-terminal')).toBe('false')
    }
  })

  it('renders the back edge (paused -> in_progress) as visually distinct from the forward edges', () => {
    const wrapper = mountDiagram(makeMachine())

    const backEdges = wrapper.findAll('[data-kind="back"]')
    expect(backEdges).toHaveLength(1)

    const forwardEdges = wrapper.findAll('[data-kind="forward"]')
    expect(forwardEdges).toHaveLength(3)

    // Distinct styling hook (dashed, in the component's scoped CSS) plus a
    // different marker than every forward edge.
    expect(backEdges[0]!.classes()).toContain('sm-edge-back')
    const backMarker = backEdges[0]!.attributes('marker-end')
    const forwardMarker = forwardEdges[0]!.attributes('marker-end')
    expect(backMarker).not.toBe(forwardMarker)
  })

  it('renders nothing when the machine has no states', () => {
    const wrapper = mountDiagram({
      key: 'empty_machine',
      entity: 'Empty',
      description: null,
      kind: 'intent',
      rules: [],
      intents: [],
      transitions: [],
      states: [],
      edges: [],
    })

    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('marks no state terminal for a fully cyclical machine (e.g. lot_position_kind)', () => {
    // Every state has an outgoing transition, so none of them is terminal;
    // the diagram must not invent one just to have somewhere to draw the
    // "done" styling, and the layout must not crash without a last layer to
    // pull a terminal state into.
    const wrapper = mountDiagram({
      key: 'lot_position_kind',
      entity: 'Lot position kind',
      description: null,
      kind: 'intent',
      rules: [],
      intents: [],
      transitions: [],
      states: [
        { value: 'unassigned', initial: true, terminal: false },
        { value: 'external', initial: false, terminal: false },
        { value: 'internal', initial: false, terminal: false },
        { value: 'mixed', initial: false, terminal: false },
      ],
      edges: [
        { from_state: 'unassigned', to_state: 'external' },
        { from_state: 'unassigned', to_state: 'internal' },
        { from_state: 'external', to_state: 'mixed' },
        { from_state: 'internal', to_state: 'mixed' },
        { from_state: 'mixed', to_state: 'unassigned' },
      ],
    })

    const nodes = wrapper.findAll('.sm-node')
    expect(nodes).toHaveLength(4)
    for (const node of nodes) {
      expect(node.attributes('data-terminal')).toBe('false')
      expect(node.classes()).not.toContain('sm-node-terminal')
      // The double-border "terminal" rect must not be drawn either.
      expect(node.findAll('.sm-node-rect-inner')).toHaveLength(0)
    }
  })

  it('uses the translated label when the machine key has a mapped i18n prefix', () => {
    const wrapper = mountDiagram({
      key: 'production_order_status',
      entity: 'Production order',
      description: null,
      kind: 'intent',
      rules: [],
      intents: [],
      transitions: [],
      states: [{ value: 'queued', initial: true, terminal: false }],
      edges: [],
    })

    expect(wrapper.get('.sm-node-label').text()).toBe(
      i18n.global.t('production.lots.orderStatus.queued'),
    )
  })
})
