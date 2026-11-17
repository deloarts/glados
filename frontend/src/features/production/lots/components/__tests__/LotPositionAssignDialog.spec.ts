import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotPositionAssignDialog from '../LotPositionAssignDialog.vue'
import type { LotPositionResponse } from '../../../types/productionLotsResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

const position: LotPositionResponse = {
  id: 1,
  public_id: '22222222-2222-2222-2222-222222222222',
  created: '2026-07-01',
  changed: null,
  changed_by: null,
  changed_by_id: null,
  sequence: 1,
  kind: 'unassigned',
  status: 'pending',
  quantity: 5,
  quantity_completed: 0,
  quantity_remaining: 5,
  note: null,
  creator_id: 1,
  lot_id: 1,
  steps: [],
  order_item_id: null,
  order_id: null,
  order_number: '',
  supplier_name: '',
  order_item_status: '',
  order_item_closed_short: false,
  earlier_order_lines: [],
  expected_delivery_date: null,
  production_orders: [],
  actions: [],
  planned_delivery_date: null,
  planned_pickup_date: null,
}

describe('LotPositionAssignDialog', () => {
  it('renders without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(LotPositionAssignDialog, {
      attachTo: document.body,
      props: { visible: true, lotId: 1, position },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('preselects pieces and names the units by their labels', async () => {
    const wrapper = mountWithApp(LotPositionAssignDialog, {
      attachTo: document.body,
      props: { visible: true, lotId: 1, position },
    })
    await flushPromises()

    wrapper.findComponent({ name: 'OrderSelect' }).vm.$emit('update:modelValue', { id: 7 })
    await flushPromises()
    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Continue')!
      .trigger('click')
    await flushPromises()

    const unit = wrapper
      .findAllComponents({ name: 'Select' })
      .find((s) => s.props('optionLabel') === 'label')!
    expect(unit.props('modelValue')).toBe('PCS')
    const options = unit.props('options') as { value: string; label: string }[]
    expect(options.find((o) => o.value === 'PCS')!.label).toBe('PCS – Pieces')

    wrapper.unmount()
  })
})
