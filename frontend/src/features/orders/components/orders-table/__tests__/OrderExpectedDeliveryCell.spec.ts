import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'
import OrderExpectedDeliveryCell from '../OrderExpectedDeliveryCell.vue'

function mountCell(canWrite: boolean, isSettable = true) {
  return mountWithApp(OrderExpectedDeliveryCell, {
    props: {
      order: makeOrderResponse({ expected_delivery_date: null }),
      canWrite,
      isSettable,
    },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('OrderExpectedDeliveryCell', () => {
  it('offers setting the expected delivery when the order takes one', async () => {
    const wrapper = mountCell(true)

    const button = wrapper.get('[data-testid="order-set-expected-delivery"]')
    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')
    expect(wrapper.emitted('set-expected-delivery')).toHaveLength(1)
  })

  it('shows the button disabled with the missing permission without write:orders', () => {
    const wrapper = mountCell(false)

    const button = wrapper.get('[data-testid="order-set-expected-delivery"]')
    expect(button.attributes('disabled')).toBeDefined()
    const span = button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Orders.')
  })

  it('shows a placeholder when the order takes no expected delivery', () => {
    const wrapper = mountCell(true, false)

    expect(wrapper.find('[data-testid="order-set-expected-delivery"]').exists()).toBe(false)
  })
})
