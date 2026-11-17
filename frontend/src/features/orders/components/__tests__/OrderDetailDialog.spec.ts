import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeOrderResponse, makeTestRouter } from '@/test-utils/factories'
import type { OrderItemResponse, OrderResponse } from '../../types/ordersResponse'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

const getOrderMock = vi.fn<() => Promise<OrderResponse>>()
vi.mock('../../api/getOrder', () => ({
  getOrder: () => getOrderMock(),
}))

let granted = true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: () => granted }),
}))

const removeItemMock = vi.fn<(orderId: number, itemId: number, editVersion: number) => Promise<void>>()
vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({ removeItem: removeItemMock }),
}))

// This dialog uses a dedicated confirm `group` (see the component) so its
// confirm doesn't collide with whatever ConfirmDialog the many, unrelated
// host tables that embed it already render (asserted below).
const confirmRequireMock = vi.fn<(option: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import OrderDetailDialog from '../OrderDetailDialog.vue'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function makeRouter() {
  return makeTestRouter([{ path: '/procurement/orders/:id', component: RouteStub }])
}

async function mountDialog() {
  const router = makeRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(OrderDetailDialog, {
    props: { orderId: 42, visible: true },
    global: {
      plugins: [router],
      stubs: {
        OrderItemsTable: true,
        OrderItemCreateForm: true,
        DeliverItemDialog: true,
        DeliveryHistoryDialog: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('OrderDetailDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getOrderMock.mockReset().mockResolvedValue(makeOrderResponse({ status: 'ordered' }))
    removeItemMock.mockReset().mockResolvedValue(undefined)
    confirmRequireMock.mockReset()
    granted = true
  })

  it('shows Add Item disabled with the missing permission without write:orders', async () => {
    granted = false
    const wrapper = await mountDialog()

    const addItem = wrapper.findComponent({ name: 'SplitButton' })
    expect(addItem.props('disabled')).toBe(true)
    const span = addItem.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Orders.')
  })

  it('renders its own group-scoped ConfirmDialog', async () => {
    const wrapper = await mountDialog()

    const confirmDialog = wrapper.findComponent({ name: 'ConfirmDialog' })
    expect(confirmDialog.exists()).toBe(true)
    expect(confirmDialog.props('group')).toBe('order-detail')
  })

  it('confirms before removing an item, and confirming calls the store with the grouped confirm', async () => {
    const wrapper = await mountDialog()

    const table = wrapper.findComponent({ name: 'OrderItemsTable' })
    const item = { id: 7, edit_version: 3 } as OrderItemResponse
    table.vm.$emit('remove', 42, item)

    expect(removeItemMock).not.toHaveBeenCalled()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as {
      group: string
      header: string
      acceptProps: { label: string; severity: string }
      rejectProps: { label: string; severity: string }
      accept: () => Promise<void>
    }
    expect(options.group).toBe('order-detail')
    expect(options.header).toBe('Remove Item')
    expect(options.acceptProps).toEqual({ label: 'Remove Item', severity: 'danger' })
    expect(options.rejectProps).toEqual({ label: 'Cancel', severity: 'secondary' })

    await options.accept()

    expect(removeItemMock).toHaveBeenCalledWith(42, 7, 3)
  })
})
