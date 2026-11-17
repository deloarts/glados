import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'

import DeliveryHistoryDialog from '../DeliveryHistoryDialog.vue'
import CorrectDeliveryDialog from '../CorrectDeliveryDialog.vue'
import { useOrdersStore } from '../../stores/ordersStore'
import type { DeliveryRecord, OrderFile, OrderItemResponse } from '../../types/ordersResponse'

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

const getFilesMock = vi.fn<(orderId: number) => Promise<OrderFile[]>>()
const uploadPictureMock =
  vi.fn<(orderId: number, itemId: number, deliveryId: number, file: File) => Promise<OrderFile>>()
vi.mock('../../api/getOrderFiles', () => ({
  getOrderFiles: (orderId: number) => getFilesMock(orderId),
}))
vi.mock('../../api/getOrderFileBlob', () => ({
  getOrderFileBlob: async () => new Blob(['x'], { type: 'image/png' }),
}))
vi.mock('../../api/uploadDeliveryPicture', () => ({
  uploadDeliveryPicture: (orderId: number, itemId: number, deliveryId: number, file: File) =>
    uploadPictureMock(orderId, itemId, deliveryId, file),
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

function picture(overrides: Partial<OrderFile> = {}): OrderFile {
  return {
    id: 40,
    public_id: 'dddddddd-0000-0000-0000-000000000040',
    order_id: 99,
    file_name: 'damage.png',
    stored_name: 'stored.png',
    mime_type: 'image/png',
    size_bytes: 10,
    storage_path: 'orders/99/picture/stored.png',
    sha256: 'x',
    category: 'picture',
    created: '2026-02-01T10:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    delivery_id: 1,
    ...overrides,
  }
}

function line(records: DeliveryRecord[], actions: string[]): OrderItemResponse {
  return {
    id: 5,
    order_id: 99,
    status: 'delivered',
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

beforeEach(() => {
  getFilesMock.mockReset().mockResolvedValue([])
  uploadPictureMock.mockReset()
  URL.createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:picture')
  URL.revokeObjectURL = vi.fn<(url: string) => void>()
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

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

describe('DeliveryHistoryDialog damage', () => {
  it('marks a delivery whose damage was noted on the delivery note', async () => {
    const wrapper = await mountHistory(
      line([record({ damage_noted_on_delivery_note: true }), record({ id: 2 })], []),
      [Permission.RECEIVE_DELIVERIES],
    )

    expect(document.body.querySelectorAll('[data-testid="damage-noted"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('offers to report damage beside the correction', async () => {
    const wrapper = await mountHistory(line([record()], ['correct_delivery']), [
      Permission.RECEIVE_DELIVERIES,
    ])

    expect(document.body.querySelectorAll('[data-testid="report-damage"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('names a rejection after receipt in the correction column', async () => {
    const rejection = record({
      id: 2,
      quantity: -1,
      quantity_rejected: 1,
      rejection_reason: 'transport_damage',
      rejection_outcome: 'lost',
      corrects_delivery_id: 1,
    })
    const wrapper = await mountHistory(line([record(), rejection], []), [
      Permission.RECEIVE_DELIVERIES,
    ])

    expect(document.body.querySelector('[data-testid="correction-reason"]')?.textContent).toBe(
      'Rejected after receipt',
    )
    wrapper.unmount()
  })

  it('shows the pictures of each row', async () => {
    getFilesMock.mockResolvedValue([
      picture({ id: 40, delivery_id: 1 }),
      picture({ id: 41, delivery_id: 1 }),
      picture({ id: 42, delivery_id: null }),
    ])
    const wrapper = await mountHistory(line([record(), record({ id: 2 })], []), [
      Permission.RECEIVE_DELIVERIES,
    ])

    expect(document.body.querySelectorAll('[data-testid="delivery-picture"]')).toHaveLength(2)
    expect(document.body.querySelectorAll('[data-testid="add-delivery-picture"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('disables adding a picture without receive:deliveries', async () => {
    const wrapper = await mountHistory(line([record()], []), [Permission.WRITE_ORDERS])

    const button = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="add-delivery-picture"]',
    )
    expect(button?.disabled).toBe(true)
    wrapper.unmount()
  })
})

interface CorrectVm {
  mode: 'miscount' | 'damage'
  canSubmit: boolean
}

describe('CorrectDeliveryDialog damage', () => {
  it('rejects the pieces after receipt and uploads the picked pictures to the new row', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const rejectionRow = record({
      id: 7,
      quantity: -2,
      quantity_rejected: 2,
      corrects_delivery_id: 1,
    })
    const correctDelivery = vi
      .spyOn(useOrdersStore(), 'correctDelivery')
      .mockResolvedValue(line([record(), rejectionRow], []))
    uploadPictureMock.mockResolvedValue(picture({ delivery_id: 7 }))
    const wrapper = mountWithApp(CorrectDeliveryDialog, {
      pinia,
      attachTo: document.body,
      props: {
        visible: false,
        item: line([record()], ['correct_delivery']),
        record: record(),
        initialMode: 'damage',
      },
    })
    await wrapper.setProps({ visible: true })
    await flushPromises()
    const vm = wrapper.vm as unknown as CorrectVm
    expect(vm.mode).toBe('damage')

    const setup = wrapper.vm as unknown as {
      quantity: number | null
      rejectReason: string | null
      rejectOutcome: string | null
      rejectNote: string
    }
    Object.assign(setup, {
      quantity: 2,
      rejectReason: 'transport_damage',
      rejectOutcome: 'lost',
      rejectNote: ' Crushed ',
    })
    const input = document.body.querySelector<HTMLInputElement>(
      '[data-testid="correct-picture-input"]',
    )!
    const file = new File(['x'], 'damage.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(vm.canSubmit).toBe(true)

    document.body.querySelector<HTMLButtonElement>('[data-testid="correct-submit"]')!.click()
    await flushPromises()

    expect(correctDelivery).toHaveBeenCalledWith(99, 5, 1, {
      quantity: 2,
      rejection: {
        rejection_reason: 'transport_damage',
        rejection_outcome: 'lost',
        rejection_note: 'Crushed',
      },
    })
    expect(uploadPictureMock).toHaveBeenCalledWith(99, 5, 7, file)
    expect(wrapper.emitted('corrected')).toHaveLength(1)
    wrapper.unmount()
  })

  it('needs a reason and an outcome, but no free-text reason', async () => {
    const pinia = signIn([Permission.RECEIVE_DELIVERIES])
    const wrapper = mountWithApp(CorrectDeliveryDialog, {
      pinia,
      attachTo: document.body,
      props: {
        visible: false,
        item: line([record()], ['correct_delivery']),
        record: record(),
        initialMode: 'damage',
      },
    })
    await wrapper.setProps({ visible: true })
    const vm = wrapper.vm as unknown as CorrectVm & {
      quantity: number | null
      rejectReason: string | null
      rejectOutcome: string | null
    }

    vm.quantity = 1
    vm.rejectReason = 'supplier_damage'
    expect(vm.canSubmit).toBe(false)
    vm.rejectOutcome = 'redeliver'
    expect(vm.canSubmit).toBe(true)
    wrapper.unmount()
  })
})
