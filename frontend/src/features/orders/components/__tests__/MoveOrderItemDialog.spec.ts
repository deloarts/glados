import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'

import type { OrderItemResponse, OrderResponse } from '../../types/ordersResponse'

const moveItemMock = vi.fn<(item: OrderItemResponse, target: OrderResponse) => Promise<void>>()
vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({ moveItem: moveItemMock }),
}))

const target = makeOrderResponse({ id: 77, supplier_id: 2 })
// The order picker is replaced by one that picks the target at once.
vi.mock('../OrderSelect.vue', () => ({
  default: defineComponent({
    name: 'OrderSelect',
    props: { statuses: { type: Array, default: undefined } },
    emits: ['update:modelValue'],
    mounted() {
      this.$emit('update:modelValue', target)
    },
    render: () => h('div'),
  }),
}))

import MoveOrderItemDialog from '../MoveOrderItemDialog.vue'

async function openFor(item: OrderItemResponse) {
  const wrapper = mountWithApp(MoveOrderItemDialog, {
    props: { visible: true, item },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

/** The dialog renders into the body. */
function moveDisabled(): boolean {
  return document.body.querySelector<HTMLButtonElement>('[data-testid="move-item-confirm"]')!
    .disabled
}

describe('MoveOrderItemDialog', () => {
  beforeEach(() => {
    moveItemMock.mockReset().mockResolvedValue()
  })

  it('moves an ordered line to another supplier only once its old supplier is settled', async () => {
    const wrapper = await openFor(
      makeOrderItemResponse({ status: 'ordered', supplier_id: 1, supplier_name: 'Contoso' }),
    )

    expect(document.body.textContent).toContain('Contoso')
    expect(moveDisabled()).toBe(true)

    await wrapper.findComponent({ name: 'Checkbox' }).vm.$emit('update:modelValue', true)
    await flushPromises()

    expect(moveDisabled()).toBe(false)
    wrapper.unmount()
  })

  it('lists only the target orders a user without manage:orders may move the line to', async () => {
    const wrapper = await openFor(makeOrderItemResponse({ status: 'ordered', supplier_id: 1 }))

    expect(wrapper.findComponent({ name: 'OrderSelect' }).props('statuses')).toEqual([
      'draft',
      'requested',
    ])
    wrapper.unmount()
  })

  it('moves a line that is not ordered yet without the confirmation', async () => {
    const wrapper = await openFor(makeOrderItemResponse({ status: 'pending', supplier_id: 1 }))

    expect(wrapper.findComponent({ name: 'Checkbox' }).exists()).toBe(false)
    expect(moveDisabled()).toBe(false)
    wrapper.unmount()
  })
})
