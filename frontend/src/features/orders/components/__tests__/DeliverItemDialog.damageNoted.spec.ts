import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse } from '@/test-utils/factories'

const deliverItemMock = vi.fn<(...args: unknown[]) => Promise<void>>()

vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({
    deliverItem: deliverItemMock,
  }),
}))

import DeliverItemDialog from '../DeliverItemDialog.vue'

async function mountDialog() {
  const item = makeOrderItemResponse({
    quantity: 4,
    quantity_delivered: 0,
    quantity_rejected: 0,
    quantity_rejected_lost: 0,
  })
  const wrapper = mountWithApp(DeliverItemDialog, {
    attachTo: document.body,
    props: { visible: false, orderId: item.order_id, item },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

async function clickDeliver(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  await buttons.at(-1)!.trigger('click')
  await flushPromises()
}

describe('DeliverItemDialog damage noted on the delivery note', () => {
  beforeEach(() => {
    deliverItemMock.mockReset()
    deliverItemMock.mockResolvedValue(undefined)
  })

  it('sends the flag when it is ticked', async () => {
    const wrapper = await mountDialog()
    ;(wrapper.vm as unknown as { damageNoted: boolean }).damageNoted = true
    await flushPromises()

    await clickDeliver(wrapper)

    expect(deliverItemMock).toHaveBeenCalledWith(
      99,
      1,
      4,
      undefined,
      expect.objectContaining({ damage_noted_on_delivery_note: true, quantity_rejected: 0 }),
    )
    wrapper.unmount()
  })

  it('starts unticked each time the dialog opens', async () => {
    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as { damageNoted: boolean }
    vm.damageNoted = true
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    expect(vm.damageNoted).toBe(false)
    wrapper.unmount()
  })
})
