import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: [] }),
)

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import ProductionOrderSplitDialog from '../ProductionOrderSplitDialog.vue'
import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({ quantity: 30, ...overrides })
}

function mountDialog(order: ProductionOrderResponse) {
  return mountWithApp(ProductionOrderSplitDialog, {
    attachTo: document.body,
    props: { visible: true, order },
  })
}

describe('ProductionOrderSplitDialog', () => {
  it('defaults to two parts summing to the order quantity', async () => {
    const wrapper = mountDialog(makeOrder({ quantity: 30 }))
    await flushPromises()

    const quantityInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(quantityInputs).toHaveLength(2)
    expect(quantityInputs[0]!.props('modelValue')).toBe(15)
    expect(quantityInputs[1]!.props('modelValue')).toBe(15)

    wrapper.unmount()
  })

  it('splits an odd quantity into whole pieces that still sum to the order', async () => {
    const wrapper = mountDialog(makeOrder({ quantity: 3 }))
    await flushPromises()

    const quantityInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(quantityInputs[0]!.props('modelValue')).toBe(1)
    expect(quantityInputs[1]!.props('modelValue')).toBe(2)

    wrapper.unmount()
  })

  it('removing a middle row keeps the remaining rows their own entered quantities', async () => {
    const wrapper = mountDialog(makeOrder({ quantity: 60 }))
    await flushPromises()

    const addButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Add Part',
    )
    expect(addButton).toBeTruthy()
    addButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    let quantityInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(quantityInputs).toHaveLength(3)
    quantityInputs[0]!.vm.$emit('update:modelValue', 10)
    quantityInputs[1]!.vm.$emit('update:modelValue', 5)
    quantityInputs[2]!.vm.$emit('update:modelValue', 15)
    await flushPromises()

    const removeButtons = Array.from(document.body.querySelectorAll('button')).filter(
      (b) => b.getAttribute('aria-label') === 'Remove Part',
    )
    expect(removeButtons).toHaveLength(3)
    // Remove the middle row (originally holding quantity 5).
    removeButtons[1]!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    quantityInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(quantityInputs).toHaveLength(2)
    expect(quantityInputs[0]!.props('modelValue')).toBe(10)
    expect(quantityInputs[1]!.props('modelValue')).toBe(15)

    wrapper.unmount()
  })

  it('submits the entered quantities on save', async () => {
    const wrapper = mountDialog(makeOrder({ id: 7, quantity: 30 }))
    await flushPromises()

    const quantityInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    quantityInputs[0]!.vm.$emit('update:modelValue', 12)
    quantityInputs[1]!.vm.$emit('update:modelValue', 18)
    await flushPromises()

    const saveButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Save')
    await saveButton!.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-orders/7/split', {
      quantities: [12, 18],
    })

    wrapper.unmount()
  })
})
