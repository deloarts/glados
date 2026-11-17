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

const getStateMachinesMock = vi.fn<() => Promise<StateMachinesResponse>>()

vi.mock('../../api/getStateMachines', () => ({
  getStateMachines: () => getStateMachinesMock(),
}))

import StateTransitionsEmbed from '../StateTransitionsEmbed.vue'

function makeLot(): StateMachineResponse {
  return {
    key: 'lot_status',
    entity: 'Lot',
    kind: 'derived',
    description: null,
    states: [
      { value: 'draft', initial: true, terminal: false },
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
    ],
    intents: [
      {
        action: 'cancel',
        text_key: 'lot.cancel',
        allowed_from: ['draft'],
        condition: 'no good piece yet',
        permission: 'manage:lots',
        effect: 'canceled_at',
        target: null,
      },
    ],
    transitions: [
      {
        from_state: 'draft',
        to_state: 'canceled',
        trigger: 'cancel_lot_request',
        subject: 'lot_status',
        cascade: false,
        rule_text_keys: ['lot_status.r1'],
        intent_text_keys: ['lot.cancel'],
        implications: [
          { machine: 'production_order_status', from_state: 'queued', to_state: 'canceled' },
        ],
      },
      {
        from_state: null,
        to_state: 'draft',
        trigger: 'cancel_production_order',
        subject: 'production_order_status',
        cascade: true,
        rule_text_keys: [],
        intent_text_keys: [],
        implications: [],
      },
    ],
  }
}

function makeProductionOrder(): StateMachineResponse {
  return {
    key: 'production_order_status',
    entity: 'Production order',
    kind: 'intent',
    description: null,
    states: [
      { value: 'queued', initial: true, terminal: false },
      { value: 'canceled', initial: false, terminal: true },
    ],
    edges: [],
    rules: [],
    intents: [],
    transitions: [
      {
        from_state: 'queued',
        to_state: 'canceled',
        trigger: 'cancel_lot_request',
        subject: 'lot_status',
        cascade: true,
        rule_text_keys: [],
        intent_text_keys: [],
        implications: [],
      },
    ],
  }
}

function mountEmbed(props: { machineKey?: string; cascades?: boolean }) {
  return mount(StateTransitionsEmbed, {
    props,
    global: {
      plugins: [i18n, [OpenVue, { theme: { preset: Aura } }]],
    },
  })
}

describe('StateTransitionsEmbed', () => {
  afterEach(() => {
    getStateMachinesMock.mockReset()
  })

  it('lists a transition with its trigger, rule, condition, permission and implications', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue({ machines: [makeLot(), makeProductionOrder()] })

    const wrapper = mountEmbed({ machineKey: 'lot_status' })
    await flushPromises()

    const row = wrapper.find('[data-trigger="cancel_lot_request"]')
    const cells = row.findAll('td').map((cell) => cell.text())
    expect(cells[0]).toBe(i18n.global.t('production.lots.status.draft'))
    expect(cells[1]).toBe(i18n.global.t('production.lots.status.canceled'))
    expect(cells[2]).toBe(i18n.global.t('stateMachines.triggers.cancel_lot_request'))
    expect(cells[3]).toContain(i18n.global.t('stateMachines.rows.lot_status.r1'))
    expect(cells[3]).toContain(i18n.global.t('stateMachines.intentRows.lot.cancel.condition'))
    expect(cells[4]).toBe(i18n.global.t('stateMachines.intentRows.lot.cancel.permission'))
    expect(cells[5]).toContain(i18n.global.t('stateMachines.machines.production_order_status'))
    wrapper.unmount()
  })

  it('names the record a cascade row came from and shows a new record as new', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue({ machines: [makeLot(), makeProductionOrder()] })

    const wrapper = mountEmbed({ machineKey: 'lot_status' })
    await flushPromises()

    const row = wrapper.find('[data-trigger="cancel_production_order"]')
    expect(row.classes()).toContain('sm-table-cascade')
    expect(row.find('[data-testid="sm-cascade"]').text()).toBe(
      i18n.global.t('stateMachines.transitions.via', {
        machine: i18n.global.t('stateMachines.machines.production_order_status'),
      }),
    )
    expect(row.findAll('td')[0]!.text()).toBe(i18n.global.t('stateMachines.transitions.created'))
    wrapper.unmount()
  })

  it('groups the cascades of every machine by the record and action behind them', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue({ machines: [makeLot(), makeProductionOrder()] })

    const wrapper = mountEmbed({ cascades: true })
    await flushPromises()

    const rows = wrapper.findAll('[data-testid="sm-cascade-table"] tbody tr')
    expect(rows.map((row) => [row.attributes('data-subject'), row.attributes('data-trigger')])).toEqual(
      [
        ['lot_status', 'cancel_lot_request'],
        ['production_order_status', 'cancel_production_order'],
      ],
    )
    expect(rows[0]!.text()).toContain(i18n.global.t('stateMachines.machines.production_order_status'))
    wrapper.unmount()
  })

  it('warns when the machine is not in the response', async () => {
    setActivePinia(createPinia())
    getStateMachinesMock.mockResolvedValue({ machines: [makeLot()] })

    const wrapper = mountEmbed({ machineKey: 'order_status' })
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('stateMachines.missing'))
    wrapper.unmount()
  })
})
