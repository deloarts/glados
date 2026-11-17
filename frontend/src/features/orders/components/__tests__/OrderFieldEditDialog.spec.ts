import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'

import type { OrderResponse } from '../../types/ordersResponse'
import type { OrderUpdateRequest } from '../../types/ordersRequest'

const updateMock = vi.fn<(id: number, payload: OrderUpdateRequest) => Promise<OrderResponse>>()
vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({ update: updateMock }),
}))

import OrderFieldEditDialog from '../OrderFieldEditDialog.vue'

/**
 * Structural, matching how `useOrderEditFields` types its own template ref,
 * so the test drives the dialog the same way its real caller does.
 */
interface OrderFieldEditDialogVm {
  open(order: OrderResponse, field: 'expected_delivery_date'): void
}

async function openDialog(order: OrderResponse) {
  const wrapper = mountWithApp(OrderFieldEditDialog, { attachTo: document.body })
  ;(wrapper.vm as unknown as OrderFieldEditDialogVm).open(order, 'expected_delivery_date')
  await flushPromises()
  return wrapper
}

async function clickSave(wrapper: Awaited<ReturnType<typeof openDialog>>) {
  await wrapper.findAllComponents({ name: 'Button' }).at(-1)!.trigger('click')
  await flushPromises()
}

describe('OrderFieldEditDialog', () => {
  beforeEach(() => {
    updateMock.mockReset().mockResolvedValue(makeOrderResponse({ status: 'ordered' }))
  })

  it('propagates the unchanged header date to items when the checkbox stays checked', async () => {
    const wrapper = await openDialog(
      makeOrderResponse({ status: 'ordered', expected_delivery_date: '2026-02-10' }),
    )

    // Checkbox defaults to checked and the date picker is left untouched:
    // the flag must not suppress propagation of a pre-filled date.
    await clickSave(wrapper)

    expect(updateMock).toHaveBeenCalledWith(42, {
      expected_delivery_date: '2026-02-10',
      update_items_delivery_date: true,
      expected_edit_version: 0,
    })

    wrapper.unmount()
  })

  it('does not propagate when the checkbox is unchecked', async () => {
    const wrapper = await openDialog(
      makeOrderResponse({ status: 'ordered', expected_delivery_date: '2026-02-10' }),
    )

    await wrapper.findComponent({ name: 'Checkbox' }).vm.$emit('update:modelValue', false)
    await clickSave(wrapper)

    expect(updateMock).toHaveBeenCalledWith(42, {
      expected_delivery_date: '2026-02-10',
      update_items_delivery_date: false,
      expected_edit_version: 0,
    })

    wrapper.unmount()
  })
})
