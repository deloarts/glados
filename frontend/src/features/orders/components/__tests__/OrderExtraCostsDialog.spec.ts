import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'

import type { OrderResponse } from '../../types/ordersResponse'
import type { OrderExtraCostsUpdateRequest } from '../../types/ordersRequest'

const setExtraCostsMock =
  vi.fn<(id: number, payload: OrderExtraCostsUpdateRequest) => Promise<OrderResponse>>()
vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({ setExtraCosts: setExtraCostsMock }),
}))

import OrderExtraCostsDialog from '../OrderExtraCostsDialog.vue'

interface OrderExtraCostsDialogVm {
  open(order: OrderResponse): void
}

async function openDialog(order: OrderResponse) {
  const wrapper = mountWithApp(OrderExtraCostsDialog, { attachTo: document.body })
  ;(wrapper.vm as unknown as OrderExtraCostsDialogVm).open(order)
  await flushPromises()
  return wrapper
}

function saveButton(): HTMLButtonElement {
  const buttons = [...document.body.querySelectorAll('button')]
  return buttons.find((b) => b.textContent?.trim() === 'Save') as HTMLButtonElement
}

describe('OrderExtraCostsDialog', () => {
  beforeEach(() => {
    setExtraCostsMock.mockReset().mockResolvedValue(makeOrderResponse())
  })

  it('saves the costs it was opened with, in cents and with the edit version', async () => {
    const line = makeOrderItemResponse({ id: 7, position: 1 })
    const wrapper = await openDialog(
      makeOrderResponse({
        edit_version: 3,
        items: [line],
        extra_costs: [
          {
            id: 1,
            public_id: 'eeeeeeee-0000-0000-0000-000000000001',
            kind: 'shipping',
            amount: 1500,
            position: 1,
            label: null,
            note: null,
            order_item_id: null,
          },
          {
            id: 2,
            public_id: 'eeeeeeee-0000-0000-0000-000000000002',
            kind: 'setup',
            amount: 9000,
            position: 2,
            label: 'Tooling',
            note: 'once',
            order_item_id: 7,
          },
        ],
      }),
    )

    saveButton().click()
    await flushPromises()

    expect(setExtraCostsMock).toHaveBeenCalledWith(42, {
      expected_edit_version: 3,
      costs: [
        { kind: 'shipping', amount: 1500, label: null, note: null, order_item_id: null },
        { kind: 'setup', amount: 9000, label: 'Tooling', note: 'once', order_item_id: 7 },
      ],
    })
    wrapper.unmount()
  })

  it('refuses a cost without an amount before calling the server', async () => {
    const wrapper = await openDialog(makeOrderResponse())
    const add = [...document.body.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Add Cost',
    ) as HTMLButtonElement
    add.click()
    await flushPromises()

    saveButton().click()
    await flushPromises()

    expect(setExtraCostsMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Every cost needs an amount above zero.')
    wrapper.unmount()
  })
})
