import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { ScheduleBoardOrderResponse } from '../../../types/scheduleBoardResponse'

// MadeItemThumbnailCell (rendered per row) pulls its files through
// madeItemFilesStore, which hits @/core/api. It is mocked generically here
// the same way ProductionOrderCompletionDialog.spec.ts does, since the
// errors it would otherwise throw are swallowed internally anyway and only
// add noise to the test run.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MachineOrdersDialog from '../MachineOrdersDialog.vue'

function makeOrder(overrides: Partial<ScheduleBoardOrderResponse> = {}): ScheduleBoardOrderResponse {
  return {
    order_id: 1,
    production_order_number: 'PO-1',
    lot_id: 1,
    lot_number: 'LOT-1',
    project_number: 'P-1',
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    made_item_revision: 'A',
    quantity: 10,
    queue_sequence: 1,
    status: 'queued',
    pinned: false,
    planned_start: '2026-08-24T00:00:00Z',
    planned_end: '2026-08-25T00:00:00Z',
    lot_position_sequence: 1,
    lot_position_count: 1,
    conflicts: [],
    machine_pool_id: 5,
    is_floating: true,
    trial_machine_id: 1,
    ...overrides,
  }
}

function mountDialog(orders: ScheduleBoardOrderResponse[], machineNamesById?: Record<number, string>) {
  return mountWithApp(MachineOrdersDialog, {
    props: { visible: true, machineName: 'Pool A', orders, machineNamesById },
    global: { directives: { tooltip: Tooltip } },
  })
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('MachineOrdersDialog', () => {
  it('falls back to the generic floating tooltip when the trial machine is not in machineNamesById', async () => {
    const wrapper = mountDialog([makeOrder({ trial_machine_id: 99 })], { 1: 'Lathe 1' })
    await flushPromises()

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.exists()).toBe(true)
    expect((tag.element as unknown as Record<string, unknown>).$_ptooltipValue).toBe(
      i18n.global.t('productionSchedule.floatingTooltip'),
    )

    wrapper.unmount()
  })

  it('falls back to the generic floating tooltip when machineNamesById is not provided at all', async () => {
    const wrapper = mountDialog([makeOrder()])
    await flushPromises()

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect((tag.element as unknown as Record<string, unknown>).$_ptooltipValue).toBe(
      i18n.global.t('productionSchedule.floatingTooltip'),
    )

    wrapper.unmount()
  })

  it('shows "Reserved on <machine>" once the trial machine resolves via machineNamesById', async () => {
    const wrapper = mountDialog([makeOrder({ trial_machine_id: 1 })], { 1: 'Lathe 1' })
    await flushPromises()

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect((tag.element as unknown as Record<string, unknown>).$_ptooltipValue).toBe(
      i18n.global.t('productionSchedule.floatingTooltipReserved', { machine: 'Lathe 1' }),
    )

    wrapper.unmount()
  })

  it('renders no floating tag at all for a resolved (non-floating) order', async () => {
    const wrapper = mountDialog([makeOrder({ is_floating: false })], { 1: 'Lathe 1' })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
