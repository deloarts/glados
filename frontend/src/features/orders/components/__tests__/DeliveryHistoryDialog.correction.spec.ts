import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'

import DeliveryHistoryDialog from '../DeliveryHistoryDialog.vue'
import CorrectDeliveryDialog from '../CorrectDeliveryDialog.vue'
import { useOrdersStore } from '../../stores/ordersStore'
import type { DeliveryRecord, OrderItemResponse } from '../../types/ordersResponse'

// The date cells load the user list for the actor's card; it stays empty
// here so the request never reaches the network.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

function record(overrides: Partial<DeliveryRecord> = {}): DeliveryRecord {
  return {
    id: 1,
    public_id: 'cccccccc-0000-0000-0000-000000000001',
    delivery_date: '2026-02-01T10:00:00Z',
    quantity: 3,
    quantity_rejected: 0,
    rejection_reason: null,
    rejection_note: null,
    rejection_outcome: null,
    storage_place: null,
    receiver_id: null,
    receiver: null,
    correction_reason: null,
    supplier_batch: null,
    delivery_note_number: null,
    certificate_reference: null,
    corrects_delivery_id: null,
    damage_noted_on_delivery_note: false,
    ...overrides,
  }
}

function line(records: DeliveryRecord[], actions: string[]): OrderItemResponse {
  return {
    id: 5,
    order_id: 99,
    status: 'partially_delivered',
    actions,
    unit: 'ST',
    quantity_delivered: 3,
    delivery_records: records,
  } as unknown as OrderItemResponse
}

function signIn(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { is_systemuser: false, permissions } as never
  return pinia
}

async function mountHistory(item: OrderItemResponse, permissions: string[]) {
  const pinia = signIn(permissions)
  const wrapper = mountWithApp(DeliveryHistoryDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: true, item },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('DeliveryHistoryDialog corrections', () => {
  it('offers a correction on an accepted delivery to a receiver while the line takes one', async () => {
    const wrapper = await mountHistory(line([record()], ['deliver', 'correct_delivery']), [
      Permission.RECEIVE_DELIVERIES,
    ])

    expect(document.body.querySelectorAll('[data-testid="correct-delivery"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('offers none when the line takes no correction', async () => {
    const closed = await mountHistory(line([record()], ['deliver']), [Permission.RECEIVE_DELIVERIES])
    expect(document.body.querySelector('[data-testid="correct-delivery"]')).toBeNull()
    closed.unmount()
  })

  it('shows the correction disabled with the missing permission to a user who cannot receive goods', async () => {
    const writer = await mountHistory(line([record()], ['correct_delivery']), [
      Permission.WRITE_ORDERS,
    ])
    const button = document.body.querySelector<HTMLButtonElement>('[data-testid="correct-delivery"]')
    expect(button?.disabled).toBe(true)
    const span = button?.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Receive Deliveries.')
    writer.unmount()
  })

  it('shows a correction row with its reason and offers no correction of it', async () => {
    const correction = record({
      id: 2,
      quantity: -1,
      corrects_delivery_id: 1,
      correction_reason: 'Counted twice',
      supplier_batch: null,
      delivery_note_number: null,
      certificate_reference: null,
    })
    const wrapper = await mountHistory(line([record(), correction], ['correct_delivery']), [
      Permission.RECEIVE_DELIVERIES,
    ])

    expect(document.body.querySelector('[data-testid="correction-reason"]')?.textContent).toBe(
      'Counted twice',
    )
    expect(document.body.querySelectorAll('[data-testid="correct-delivery"]')).toHaveLength(1)
    wrapper.unmount()
  })
})

interface CorrectVm {
  quantity: number | null
  reason: string
  canSubmit: boolean
  maxQuantity: number
  minQuantity: number
  fractionDigits: number
  submit(): Promise<void>
}

describe('CorrectDeliveryDialog', () => {
  it('books the correction for the row and closes', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const correctDelivery = vi
      .spyOn(useOrdersStore(), 'correctDelivery')
      .mockResolvedValue(line([record()], ['correct_delivery']))
    const wrapper = mountWithApp(CorrectDeliveryDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: false, item: line([record()], ['correct_delivery']), record: record() },
    })
    await wrapper.setProps({ visible: true })
    const vm = wrapper.vm as unknown as CorrectVm

    vm.quantity = 4
    vm.reason = 'Counted twice'
    expect(vm.canSubmit).toBe(false)
    vm.quantity = 2
    expect(vm.canSubmit).toBe(true)

    await vm.submit()
    await flushPromises()

    expect(correctDelivery).toHaveBeenCalledWith(99, 5, 1, { quantity: 2, reason: 'Counted twice' })
    expect(wrapper.emitted('corrected')).toHaveLength(1)
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
    wrapper.unmount()
  })

  it('takes whole pieces in a counted unit or on a MADE line and three decimals otherwise', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const cases: [Partial<OrderItemResponse>, number, number][] = [
      [{ unit: 'PCS', line_type: 'BOUGHT' }, 1, 0],
      [{ unit: 'pcs', line_type: 'SOURCE' }, 1, 0],
      [{ unit: 'KG', line_type: 'MADE' }, 1, 0],
      [{ unit: 'KG', line_type: 'SOURCE' }, 0.001, 3],
    ]
    for (const [overrides, min, digits] of cases) {
      const item = { ...line([record()], ['correct_delivery']), ...overrides } as OrderItemResponse
      const wrapper = mountWithApp(CorrectDeliveryDialog, {
        pinia,
        attachTo: document.body,
        props: { visible: true, item, record: record() },
      })
      const vm = wrapper.vm as unknown as CorrectVm
      expect([overrides.unit, vm.minQuantity, vm.fractionDigits]).toEqual([overrides.unit, min, digits])
      vm.reason = 'Counted twice'
      vm.quantity = 0.5
      expect(vm.canSubmit).toBe(digits !== 0)
      wrapper.unmount()
    }
  })

  it('needs a reason', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const wrapper = mountWithApp(CorrectDeliveryDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: true, item: line([record()], ['correct_delivery']), record: record() },
    })
    const vm = wrapper.vm as unknown as CorrectVm

    vm.quantity = 1
    vm.reason = '   '

    expect(vm.canSubmit).toBe(false)
    wrapper.unmount()
  })

  it('bounds the quantity by what earlier corrections of the row left and by the delivered total', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const row = record({ id: 1, quantity: 5 })
    const earlier = record({ id: 2, quantity: -2, corrects_delivery_id: 1 })
    const other = record({ id: 3, quantity: -1, corrects_delivery_id: 9 })
    const item = {
      ...line([row, earlier, other], ['correct_delivery']),
      quantity_delivered: 10,
    } as OrderItemResponse
    const wrapper = mountWithApp(CorrectDeliveryDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: true, item, record: row },
    })
    const vm = wrapper.vm as unknown as CorrectVm

    expect(vm.maxQuantity).toBe(3)
    await wrapper.setProps({ item: { ...item, quantity_delivered: 2 } as OrderItemResponse })
    expect(vm.maxQuantity).toBe(2)
    wrapper.unmount()
  })

  it('caps the reason at the length the backend stores', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const item = { ...line([record()], ['correct_delivery']), quantity_delivered: 3 }
    const wrapper = mountWithApp(CorrectDeliveryDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: false, item: item as OrderItemResponse, record: record() },
    })
    await wrapper.setProps({ visible: true })
    await flushPromises()
    const vm = wrapper.vm as unknown as CorrectVm

    const reason = document.body.querySelector('#correct-reason')
    expect(reason?.getAttribute('maxlength')).toBe('1000')
    vm.quantity = 1
    vm.reason = 'x'.repeat(1001)
    expect(vm.canSubmit).toBe(false)
    vm.reason = 'x'.repeat(1000)
    expect(vm.canSubmit).toBe(true)
    wrapper.unmount()
  })
})
