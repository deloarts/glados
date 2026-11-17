import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

const mergeMock = vi.fn<(payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))
vi.mock('../../../api/mergeProductionOrders', () => ({
  mergeProductionOrders: (payload: unknown) => mergeMock(payload),
}))

import ProductionOrderMergeDialog from '../ProductionOrderMergeDialog.vue'
import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

// What the backend offers on a production order in each status, from the
// production order intent table (start and resume also need the lot, the
// machine and upstream input, which can_start reports).
const ORDER_ACTIONS: Record<string, LifecycleAction[]> = {
  queued: ['start', 'cancel', 'split', 'merge'],
  in_progress: ['pause', 'cancel', 'record_completion', 'scrap'],
  paused: ['resume', 'cancel'],
  completed: [],
  canceled: [],
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    actions: ORDER_ACTIONS[overrides.status ?? 'queued'],
    quantity: 30,
    ...overrides,
  })
}

function mountDialog(order: ProductionOrderResponse, orders: ProductionOrderResponse[]) {
  return mountWithApp(ProductionOrderMergeDialog, {
    attachTo: document.body,
    props: { visible: true, order, orders: [order, ...orders] },
  })
}

function offeredNumbers(): string[] {
  return Array.from(document.body.querySelectorAll('.sibling-row label')).map(
    (label) => label.textContent?.split(',')[0]?.trim() ?? '',
  )
}

describe('ProductionOrderMergeDialog', () => {
  it('offers only queued orders of the same machine, pool and lot position', async () => {
    const order = makeOrder({ machine_pool_id: 5 })
    const wrapper = mountDialog(order, [
      makeOrder({ id: 2, production_order_number: 'PO-2', machine_pool_id: 5 }),
      makeOrder({ id: 3, production_order_number: 'PO-3', machine_pool_id: 6 }),
      makeOrder({ id: 4, production_order_number: 'PO-4', machine_pool_id: null }),
      makeOrder({ id: 5, production_order_number: 'PO-5', machine_pool_id: 5, machine_id: 2 }),
      makeOrder({ id: 6, production_order_number: 'PO-6', machine_pool_id: 5, lot_position_id: 9 }),
      makeOrder({ id: 7, production_order_number: 'PO-7', machine_pool_id: 5, status: 'paused' }),
    ])
    await flushPromises()

    expect(offeredNumbers()).toEqual(['PO-2'])

    wrapper.unmount()
  })

  it('labels each sibling with its number and quantity, with no stray space', async () => {
    const order = makeOrder({ machine_pool_id: null })
    const wrapper = mountDialog(order, [
      makeOrder({ id: 2, production_order_number: 'PO-2', machine_pool_id: null, quantity: 5 }),
    ])
    await flushPromises()

    const label = document.body.querySelector('.sibling-row label')
    expect(label?.textContent?.trim()).toMatch(/^PO-2, \S/)

    wrapper.unmount()
  })

  it('keeps orders of a pool away from an order without one', async () => {
    const order = makeOrder({ machine_pool_id: null })
    const wrapper = mountDialog(order, [
      makeOrder({ id: 2, production_order_number: 'PO-2', machine_pool_id: null }),
      makeOrder({ id: 3, production_order_number: 'PO-3', machine_pool_id: 5 }),
    ])
    await flushPromises()

    expect(offeredNumbers()).toEqual(['PO-2'])

    wrapper.unmount()
  })

  it('sends the edit version of every merged order as it shows them', async () => {
    mergeMock.mockResolvedValue(makeOrder({ id: 1 }))
    const order = makeOrder({ id: 1, edit_version: 3 })
    const wrapper = mountDialog(order, [
      makeOrder({ id: 2, production_order_number: 'PO-2', edit_version: 7 }),
    ])
    await flushPromises()

    ;(document.body.querySelector('#sibling-2') as HTMLInputElement).click()
    await flushPromises()
    const submit = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Merge')
    await submit!.trigger('click')
    await flushPromises()

    expect(mergeMock).toHaveBeenCalledWith({
      production_order_ids: [1, 2],
      expected_edit_versions: { 1: 3, 2: 7 },
    })

    wrapper.unmount()
  })
})
