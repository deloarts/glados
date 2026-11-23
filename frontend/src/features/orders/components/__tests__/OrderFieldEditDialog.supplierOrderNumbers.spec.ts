import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'

import type { OrderResponse } from '../../types/ordersResponse'
import type {
  OrderSupplierOrderNumbersUpdateRequest,
  OrderUpdateRequest,
} from '../../types/ordersRequest'

const updateMock = vi.fn<(id: number, payload: OrderUpdateRequest) => Promise<OrderResponse>>()
const setNumbersMock =
  vi.fn<(id: number, payload: OrderSupplierOrderNumbersUpdateRequest) => Promise<OrderResponse>>()
vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({ update: updateMock, setSupplierOrderNumbers: setNumbersMock }),
}))

import OrderFieldEditDialog from '../OrderFieldEditDialog.vue'

interface OrderFieldEditDialogVm {
  open(order: OrderResponse, field: 'supplier_order_numbers'): void
}

async function openDialog(order: OrderResponse) {
  const wrapper = mountWithApp(OrderFieldEditDialog, { attachTo: document.body })
  ;(wrapper.vm as unknown as OrderFieldEditDialogVm).open(order, 'supplier_order_numbers')
  await flushPromises()
  return wrapper
}

async function clickSave(wrapper: Awaited<ReturnType<typeof openDialog>>) {
  await wrapper.findAllComponents({ name: 'Button' }).at(-1)!.trigger('click')
  await flushPromises()
}

function numbersInput(): HTMLInputElement {
  return document.body.querySelector('[data-testid="text-chips-input"] input') as HTMLInputElement
}

describe('OrderFieldEditDialog, supplier order numbers', () => {
  beforeEach(() => {
    updateMock.mockReset()
    setNumbersMock.mockReset().mockResolvedValue(makeOrderResponse({ status: 'ordered' }))
  })

  it('saves the numbers through their own endpoint with the edit version read', async () => {
    const wrapper = await openDialog(
      makeOrderResponse({ status: 'ordered', edit_version: 3, supplier_order_numbers: ['AB-1'] }),
    )

    await clickSave(wrapper)

    expect(setNumbersMock).toHaveBeenCalledWith(42, { numbers: ['AB-1'], expected_edit_version: 3 })
    expect(updateMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('takes a number typed but not confirmed yet on save', async () => {
    const wrapper = await openDialog(
      makeOrderResponse({ status: 'ordered', supplier_order_numbers: ['AB-1'] }),
    )

    numbersInput().value = 'AB-2'
    await clickSave(wrapper)

    expect(setNumbersMock).toHaveBeenCalledWith(42, {
      numbers: ['AB-1', 'AB-2'],
      expected_edit_version: 0,
    })
    wrapper.unmount()
  })

  it('does not change the order it was opened with before saving', async () => {
    const order = makeOrderResponse({ status: 'ordered', supplier_order_numbers: ['AB-1'] })
    const wrapper = await openDialog(order)

    numbersInput().value = 'AB-2'
    await clickSave(wrapper)

    expect(order.supplier_order_numbers).toEqual(['AB-1'])
    wrapper.unmount()
  })
})
