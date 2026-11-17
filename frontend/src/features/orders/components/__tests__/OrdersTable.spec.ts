import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse, makeOrderResponse, makeTestRouter } from '@/test-utils/factories'
import { useOrdersFiltersStore } from '../../stores/ordersFiltersStore'
import type { OrderResponse } from '../../types/ordersResponse'

// OrdersTable pulls `items`/`total` through `storeToRefs(ordersStore)`, which
// needs a real Pinia store (a plain mocked object won't behave like one),
// so, unlike OrderDetailView/OrderDetailDialog's specs, this one mocks the
// API layer underneath the real store instead of the store itself.
const apiGetMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()
const apiPutMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()
const apiDeleteMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => apiGetMock(url),
    put: (url: string) => apiPutMock(url),
    delete: (url: string) => apiDeleteMock(url),
  },
}))

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: () => true }),
}))

// `confirm.require`'s conventional shape is asserted directly on the mock
// call, same approach as OrderDetailView/OrderDetailDialog's specs.
// OrdersTable itself renders no <ConfirmDialog/>; its
// parent (OrdersView.vue) does, so there's nothing to mount here either way.
const confirmRequireMock = vi.fn<(option: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import OrdersTable from '../OrdersTable.vue'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

// What the backend offers a manager of orders on an order in each status.
const ORDER_ACTIONS: Record<OrderResponse['status'], LifecycleAction[]> = {
  draft: ['mark_requested', 'mark_ordered', 'cancel'],
  requested: ['mark_ordered', 'cancel'],
  partially_ordered: ['mark_ordered', 'cancel', 'deliver'],
  ordered: ['cancel', 'deliver'],
  partially_delivered: ['cancel', 'deliver'],
  delivered: [],
  canceled: [],
}

function makeOrder(overrides: Partial<OrderResponse> = {}): OrderResponse {
  return makeOrderResponse({
    actions: ORDER_ACTIONS[overrides.status ?? 'ordered'],
    status: 'ordered',
    items: [
      makeOrderItemResponse({
        id: 9,
        public_id: 'dddddddd-0000-0000-0000-000000000009',
        actions: ['mark_requested', 'mark_ordered', 'cancel', 'edit_quantity', 'move', 'remove'],
        quantity: 1,
        price: 100,
        order_id: 42,
        supplier_name: 'ACME Supplies',
      }),
    ],
    ...overrides,
  })
}

async function mountTable(order: OrderResponse) {
  apiGetMock.mockImplementation((url: string) => {
    if (url === '/orders/') return Promise.resolve({ data: { items: [order], total: 1 } })
    if (url === `/orders/${order.id}`) return Promise.resolve({ data: order })
    return Promise.resolve({ data: { items: [], total: 0 } })
  })
  apiPutMock.mockResolvedValue({ data: order })
  apiDeleteMock.mockResolvedValue({ data: undefined })

  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  // The row-level action column (the cancel button included) is hidden by
  // default, same as the orders list itself. Switch it on so this test can
  // reach it without going through the row context menu.
  useOrdersFiltersStore().showActions = true

  const wrapper = mountWithApp(OrdersTable, {
    pinia,
    global: {
      plugins: [router],
    },
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

describe('OrdersTable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiGetMock.mockReset()
    apiPutMock.mockReset()
    apiDeleteMock.mockReset()
    confirmRequireMock.mockReset()
  })

  it('confirms before canceling an order, and confirming calls the same store action', async () => {
    const order = makeOrder({ status: 'ordered' })
    const wrapper = await mountTable(order)

    const cancelButton = wrapper.find('button[aria-label="Cancel Order"]')
    expect(cancelButton.exists()).toBe(true)
    await cancelButton.trigger('click')

    expect(apiPutMock).not.toHaveBeenCalled()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as {
      header: string
      acceptProps: { label: string; severity: string }
      rejectProps: { label: string; severity: string }
      accept: () => Promise<void>
    }
    expect(options.header).toBe('Cancel Order')
    expect(options.acceptProps).toEqual({ label: 'Cancel Order', severity: 'danger' })
    expect(options.rejectProps).toEqual({ label: 'Cancel', severity: 'secondary' })

    await options.accept()

    expect(apiPutMock).toHaveBeenCalledWith(`/orders/${order.id}/cancel`)
  })

  it('offers to notify the supplier with a second confirm once the cancel succeeds', async () => {
    const order = makeOrder({ status: 'ordered' })
    const wrapper = await mountTable(order)

    const cancelButton = wrapper.find('button[aria-label="Cancel Order"]')
    await cancelButton.trigger('click')

    const cancelOptions = confirmRequireMock.mock.calls[0]![0] as { accept: () => Promise<void> }
    await cancelOptions.accept()
    await flushPromises()

    // A second, independent confirm.require() call (not folded into the
    // cancel one), offering to compose the cancellation mail. See
    // useOrderMailComposer.spec.ts's `order_canceled` describe block for
    // what accepting it actually resolves/sends.
    expect(confirmRequireMock).toHaveBeenCalledTimes(2)
    const notifyOptions = confirmRequireMock.mock.calls[1]![0] as {
      header: string
      message: string
    }
    expect(notifyOptions.header).toBe('Notify Supplier?')
    expect(notifyOptions.message).toBe(
      'Would you like to send a cancellation notice to the supplier?',
    )
  })

  it('confirms before removing an item, and confirming calls the same store action', async () => {
    const order = makeOrder()
    const wrapper = await mountTable(order)

    const expandButton = wrapper.find('tbody [aria-expanded]')
    await expandButton.trigger('click')
    await flushPromises()

    const table = wrapper.findComponent({ name: 'OrderItemsTable' })
    expect(table.exists()).toBe(true)
    const item = order.items![0]
    expect(item).toBeTruthy()
    table.vm.$emit('remove', order.id, item)
    await flushPromises()

    expect(apiDeleteMock).not.toHaveBeenCalled()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as {
      header: string
      acceptProps: { label: string; severity: string }
      accept: () => Promise<void>
    }
    expect(options.header).toBe('Remove Item')
    expect(options.acceptProps).toEqual({ label: 'Remove Item', severity: 'danger' })

    await options.accept()

    expect(apiDeleteMock).toHaveBeenCalledWith(`/orders/${order.id}/items/${item!.id}`)
  })

  // selectionMode="single" makes every row keyboard-focusable (via
  // OpenVue's roving-tabindex) and gives Enter the same effect as a click;
  // both OpenVue events must still drive the table's one existing
  // @row-click behaviour (expanding the row) without double-firing it.
  it('makes the first row keyboard-focusable', async () => {
    const order = makeOrder()
    const wrapper = await mountTable(order)

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('expands the row on @row-select the same way @row-click does', async () => {
    const order = makeOrder()
    const wrapper = await mountTable(order)

    expect(wrapper.findComponent({ name: 'OrderItemsTable' }).exists()).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: order, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'OrderItemsTable' }).exists()).toBe(true)
  })

  it('does not double-invoke the row-open handler when a real click fires both row-click and row-select', async () => {
    const order = makeOrder()
    const wrapper = await mountTable(order)

    expect(wrapper.findComponent({ name: 'OrderItemsTable' }).exists()).toBe(false)

    // OpenVue's selectionMode="single" emits row-click *and* row-select
    // (in that order, synchronously) for the same click on a
    // previously-unselected row. A real click exercises both, not just
    // one in isolation. Without the row-open guard this would toggle the
    // row expanded then immediately collapsed again, netting out closed.
    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    await row.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'OrderItemsTable' }).exists()).toBe(true)
  })
})
