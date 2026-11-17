import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse } from '@/test-utils/factories'

const deliverItemMock = vi.fn<(...args: unknown[]) => Promise<void>>()

vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({
    deliverItem: deliverItemMock,
  }),
}))

import DeliverItemDialog from '../DeliverItemDialog.vue'
import type { OrderItemResponse } from '../../types/ordersResponse'

function makeItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return makeOrderItemResponse({ quantity_rejected: 0, quantity_rejected_lost: 0, ...overrides })
}

interface DialogVm {
  quantity: number | null
  showReject: boolean
  rejectedQuantity: number | null
  rejectReason: string | null
  rejectNote: string
  rejectOutcome: string | null
  createReplacement: boolean
  remaining: number
  maxDeliverable: number
  quantityCap: number | undefined
  overDelivered: number
  isMadeLine: boolean
  showCreateReplacement: boolean
  canSubmit: boolean
}

async function mountDialog(item: OrderItemResponse) {
  const wrapper = mountWithApp(DeliverItemDialog, {
    attachTo: document.body,
    props: { visible: false, orderId: item.order_id, item },
  })
  // The reset-on-open watcher only fires on a false -> true transition.
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

async function clickDeliver(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  await buttons.at(-1)!.trigger('click')
  await flushPromises()
}

describe('DeliverItemDialog', () => {
  beforeEach(() => {
    deliverItemMock.mockReset()
    deliverItemMock.mockResolvedValue(undefined)
  })

  it('starts with the reject block collapsed and no rejection fields set', async () => {
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0 }))
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.showReject).toBe(false)
    expect(vm.rejectedQuantity).toBeNull()
    expect(vm.quantity).toBe(4)

    wrapper.unmount()
  })

  it('toggles the reject block open by clicking the toggle row', async () => {
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0 }))

    // Dialog content is teleported to document.body by OpenVue, so it's
    // queried through the raw DOM rather than the wrapper's own tree.
    expect(document.body.querySelector('.reject-block')).toBeNull()
    await new DOMWrapper(document.body.querySelector('.reject-toggle')!).trigger('click')
    expect(document.body.querySelector('.reject-block')).not.toBeNull()

    wrapper.unmount()
  })

  it('blocks submit when a rejected quantity is set without a reason and outcome', async () => {
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0 }))
    const vm = wrapper.vm as unknown as DialogVm

    vm.rejectedQuantity = 1
    await flushPromises()
    expect(vm.canSubmit).toBe(false)

    vm.rejectReason = 'supplier_damage'
    vm.rejectOutcome = 'redeliver'
    await flushPromises()
    expect(vm.canSubmit).toBe(true)

    wrapper.unmount()
  })

  it('auto-clamps the delivered quantity down once a reject quantity eats into the remainder', async () => {
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0 }))
    const vm = wrapper.vm as unknown as DialogVm

    vm.rejectedQuantity = 2
    vm.rejectReason = 'supplier_damage'
    vm.rejectOutcome = 'redeliver'
    await flushPromises()
    // quantity auto-clamps down to maxDeliverable (4 - 2 = 2) once the
    // reject quantity is set, so delivered + rejected never exceeds
    // remaining through the UI. The combined total should sit at the cap.
    expect(vm.quantity).toBe(2)
    expect(vm.canSubmit).toBe(true)

    wrapper.unmount()
  })

  it('blocks submit when the rejected quantity exceeds the remaining line quantity', async () => {
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0 }))
    const vm = wrapper.vm as unknown as DialogVm

    // Assigned directly, bypassing the InputNumber's own :max clamp.
    vm.rejectedQuantity = 5
    vm.rejectReason = 'supplier_damage'
    vm.rejectOutcome = 'redeliver'
    await flushPromises()

    expect(vm.canSubmit).toBe(false)

    wrapper.unmount()
  })

  it('lets a bought line take more than it awaits and says so', async () => {
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0 }))
    const vm = wrapper.vm as unknown as DialogVm

    vm.quantity = 5
    await flushPromises()

    expect(vm.quantityCap).toBeUndefined()
    expect(vm.overDelivered).toBe(1)
    expect(vm.canSubmit).toBe(true)
    expect(document.body.textContent).toContain('That is 1 more than the line still awaits.')

    wrapper.unmount()
  })

  it('caps a MADE line at the pieces it awaits', async () => {
    const wrapper = await mountDialog(
      makeItem({ quantity: 4, quantity_delivered: 0, line_type: 'MADE' }),
    )
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.quantityCap).toBe(4)
    expect(vm.overDelivered).toBe(0)

    wrapper.unmount()
  })

  it('remaining excludes quantity already lost to a prior rejection', async () => {
    const wrapper = await mountDialog(
      makeItem({ quantity: 4, quantity_delivered: 1, quantity_rejected_lost: 1 }),
    )
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.remaining).toBe(2)
    expect(vm.quantity).toBe(2)

    wrapper.unmount()
  })

  it('says a lost quantity reopens the demand, unless a replacement lot covers it', async () => {
    const hint = 'The lost quantity is not re-delivered.'
    const wrapper = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0, line_type: 'BOUGHT' }))
    const vm = wrapper.vm as unknown as DialogVm
    vm.showReject = true
    vm.rejectOutcome = 'redeliver'
    await flushPromises()
    expect(document.body.textContent).not.toContain(hint)
    vm.rejectOutcome = 'lost'
    await flushPromises()
    expect(document.body.textContent).toContain(hint)
    wrapper.unmount()

    const made = await mountDialog(makeItem({ quantity: 4, quantity_delivered: 0, line_type: 'MADE' }))
    const madeVm = made.vm as unknown as DialogVm
    madeVm.showReject = true
    madeVm.rejectOutcome = 'lost'
    await flushPromises()
    expect(document.body.textContent).not.toContain(hint)
    madeVm.createReplacement = false
    await flushPromises()
    expect(document.body.textContent).toContain(hint)
    made.unmount()
  })

  it('shows the create-replacement checkbox only for a MADE line with outcome lost', async () => {
    const boughtItem = makeItem({ quantity: 4, quantity_delivered: 0, line_type: 'BOUGHT' })
    const wrapper = await mountDialog(boughtItem)
    const vm = wrapper.vm as unknown as DialogVm

    vm.rejectedQuantity = 1
    vm.rejectReason = 'supplier_damage'
    vm.rejectOutcome = 'lost'
    await flushPromises()
    expect(vm.showCreateReplacement).toBe(false)

    wrapper.unmount()

    const madeItem = makeItem({ quantity: 4, quantity_delivered: 0, line_type: 'MADE' })
    const madeWrapper = await mountDialog(madeItem)
    const madeVm = madeWrapper.vm as unknown as DialogVm

    madeVm.rejectedQuantity = 1
    madeVm.rejectReason = 'supplier_damage'
    madeVm.rejectOutcome = 'redeliver'
    await flushPromises()
    expect(madeVm.showCreateReplacement).toBe(false)

    madeVm.rejectOutcome = 'lost'
    await flushPromises()
    expect(madeVm.showCreateReplacement).toBe(true)

    madeWrapper.unmount()
  })

  it('sends no rejection body when nothing is rejected (existing behaviour stays unchanged)', async () => {
    const item = makeItem({ quantity: 4, quantity_delivered: 0 })
    const wrapper = await mountDialog(item)

    await clickDeliver(wrapper)

    expect(deliverItemMock).toHaveBeenCalledWith(99, 1, 4, undefined, undefined)

    wrapper.unmount()
  })

  it('sends the full rejection payload, including create_replacement, for a lost MADE-line rejection', async () => {
    const item = makeItem({ quantity: 4, quantity_delivered: 0, line_type: 'MADE' })
    const wrapper = await mountDialog(item)
    const vm = wrapper.vm as unknown as DialogVm

    vm.rejectedQuantity = 1
    vm.rejectReason = 'supplier_damage'
    vm.rejectNote = 'Dented on arrival'
    vm.rejectOutcome = 'lost'
    vm.createReplacement = false
    await flushPromises()

    await clickDeliver(wrapper)

    expect(deliverItemMock).toHaveBeenCalledWith(99, 1, 3, undefined, {
      quantity_rejected: 1,
      rejection_reason: 'supplier_damage',
      rejection_note: 'Dented on arrival',
      rejection_outcome: 'lost',
      create_replacement: false,
    })

    wrapper.unmount()
  })
})
