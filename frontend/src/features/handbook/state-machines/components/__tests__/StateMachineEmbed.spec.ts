import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'

import type {
  StateMachineResponse,
  StateMachinesResponse,
} from '../../types/stateMachinesResponse'
import { resolveRowText, resolveStateLabel } from '../../utils/stateMachineLabels'

const getStateMachinesMock = vi.fn<() => Promise<StateMachinesResponse>>()

vi.mock('../../api/getStateMachines', () => ({
  getStateMachines: () => getStateMachinesMock(),
}))

import StateMachineEmbed from '../StateMachineEmbed.vue'

function makeResponse(): StateMachinesResponse {
  return {
    machines: [
      {
        key: 'production_order_status',
        entity: 'Production order',
        description: 'Lifecycle of a production order.',
        kind: 'intent',
        rules: [],
        intents: [],
        transitions: [],
        states: [
          { value: 'queued', initial: true, terminal: false },
          { value: 'completed', initial: false, terminal: true },
        ],
        edges: [{ from_state: 'queued', to_state: 'completed' }],
      },
      {
        key: 'lot_position_kind',
        entity: 'Lot position kind',
        description: 'What kind of party executes a LotPosition.',
        kind: 'intent',
        rules: [],
        intents: [],
        transitions: [],
        states: [
          { value: 'unassigned', initial: true, terminal: false },
          { value: 'external', initial: false, terminal: false },
          { value: 'mixed', initial: false, terminal: false },
        ],
        edges: [
          { from_state: 'unassigned', to_state: 'external' },
          { from_state: 'external', to_state: 'mixed' },
          { from_state: 'mixed', to_state: 'unassigned' },
        ],
      },
    ],
  }
}

function makeDerivedMachine(): StateMachineResponse {
  return {
    key: 'lot_status',
    entity: 'Lot',
    kind: 'derived',
    description: null,
    states: [
      { value: 'draft', initial: true, terminal: false },
      { value: 'on_hold', initial: false, terminal: false },
      { value: 'canceled', initial: false, terminal: true },
    ],
    edges: [],
    rules: [
      {
        number: 1,
        text_key: 'lot_status.r1',
        condition: 'canceled_at set',
        result: 'canceled',
        results: ['canceled'],
        result_text_key: null,
      },
      {
        number: 2,
        text_key: 'lot_status.r2',
        condition: 'otherwise',
        result: 'draft',
        results: ['draft'],
        result_text_key: null,
      },
    ],
    intents: [
      {
        action: 'resume',
        text_key: 'lot.resume',
        allowed_from: ['on_hold'],
        condition: '',
        permission: '',
        effect: 'clears held_at',
        target: null,
      },
    ],
    transitions: [],
  }
}

function mountEmbed(machineKey: string) {
  return mount(StateMachineEmbed, {
    props: { machineKey },
    global: {
      plugins: [i18n, [OpenVue, { theme: { preset: Aura } }]],
    },
  })
}

afterEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
  i18n.global.locale.value = 'enGB'
})

describe('StateMachineEmbed', () => {
  it('renders only the diagram for the machine key it was given', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue(makeResponse())

    const wrapper = mountEmbed('production_order_status')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Lot position kind')
    expect(wrapper.findAll('svg.sm-diagram')).toHaveLength(1)
    expect(wrapper.findAll('.sm-node')).toHaveLength(2)
  })

  it('hides the terminal legend swatch for a machine with no terminal state', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue(makeResponse())

    const withTerminal = mountEmbed('production_order_status')
    await flushPromises()
    expect(withTerminal.text()).toContain(i18n.global.t('stateMachines.legend.terminal'))

    const withoutTerminal = mountEmbed('lot_position_kind')
    await flushPromises()
    expect(withoutTerminal.text()).not.toContain(i18n.global.t('stateMachines.legend.terminal'))
    // Initial and back-edge legend items are unaffected.
    expect(withoutTerminal.text()).toContain(i18n.global.t('stateMachines.legend.initial'))
    expect(withoutTerminal.text()).toContain(i18n.global.t('stateMachines.legend.backEdge'))
  })

  it('shows a graceful fallback when its machine key is not in the response', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue(makeResponse())

    const wrapper = mountEmbed('not_a_registered_machine')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('shows an error state when the fetch fails', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockRejectedValue(new Error('network down'))

    const wrapper = mountEmbed('production_order_status')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('refetches when the refresh button is clicked', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue(makeResponse())

    const wrapper = mountEmbed('production_order_status')
    await flushPromises()
    expect(getStateMachinesMock).toHaveBeenCalledTimes(1)

    await wrapper.get('.sm-embed-refresh button').trigger('click')
    await flushPromises()

    expect(getStateMachinesMock).toHaveBeenCalledTimes(2)
  })

  // The "as of" timestamp must not go through a bare `toLocaleTimeString()`,
  // which always follows the browser's own language regardless of the UI
  // language picked in Glados. Pinning the system clock and switching to
  // de-AT proves the label tracks the active UI locale instead.
  it('renders the "as of" timestamp in the active UI locale, not the browser default', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue(makeResponse())
    vi.useFakeTimers()
    const fixedNow = new Date(2026, 7, 6, 14, 32, 5)
    vi.setSystemTime(fixedNow)
    i18n.global.locale.value = 'deAT'

    const wrapper = mountEmbed('production_order_status')
    await flushPromises()

    const expected = new Intl.DateTimeFormat('de-AT', { timeStyle: 'medium' }).format(fixedNow)
    expect(wrapper.find('.sm-embed-as-of').text()).toContain(expected)
  })

  it('shares one fetch across two embeds on the same catalog (different machine keys)', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue(makeResponse())

    const first = mountEmbed('production_order_status')
    const second = mountEmbed('lot_position_kind')
    await flushPromises()

    expect(getStateMachinesMock).toHaveBeenCalledTimes(1)
    expect(first.findAll('svg.sm-diagram')).toHaveLength(1)
    expect(second.findAll('svg.sm-diagram')).toHaveLength(1)
  })

  it('renders a derived machine as its rule and action tables, without a diagram', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue({ machines: [makeDerivedMachine()] })
    const t = i18n.global.t as (key: string) => string
    const te = i18n.global.te as (key: string) => boolean

    const wrapper = mountEmbed('lot_status')
    await flushPromises()

    expect(wrapper.find('svg.sm-diagram').exists()).toBe(false)
    expect(wrapper.find('.sm-embed-legend').exists()).toBe(false)
    expect(wrapper.get('[data-testid="sm-kind"]').text()).toBe(t('stateMachines.kind.derived'))
    const rows = wrapper.findAll('[data-testid="sm-rule-table"] tbody tr')
    expect(rows.map((row) => row.attributes('data-rule'))).toEqual(['1', '2'])
    expect(rows[0]!.text()).toContain(resolveRowText(t, te, 'rows.lot_status.r1', 'canceled_at set'))
    expect(rows[0]!.text()).toContain(resolveStateLabel(t, te, 'lot_status', 'canceled'))
    const actions = wrapper.findAll('[data-testid="sm-intent-table"] tbody tr')
    expect(actions).toHaveLength(1)
    expect(actions[0]!.text()).toContain(resolveStateLabel(t, te, 'lot_status', 'on_hold'))
    expect(actions[0]!.text()).toContain(
      resolveRowText(t, te, 'intentRows.lot.resume.effect', 'clears held_at'),
    )
  })
})
