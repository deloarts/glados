import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import constants from '@/constants'
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

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: () => true }),
}))

// The invoice-missing hint reads the files store the side panel fills; the
// panel is stubbed here, so the store is faked per test instead.
let filesById: Record<number, unknown[]> = {}
vi.mock('../../stores/orderFilesStore', () => ({
  useOrderFilesStore: () => ({
    getFiles: (id: number) => filesById[id] ?? [],
  }),
}))

const cancelMock = vi.fn<(id: number) => Promise<void>>()
const removeItemMock = vi.fn<(orderId: number, itemId: number, editVersion: number) => Promise<void>>()
const markAllItemsRequestedMock = vi.fn<(id: number) => Promise<void>>()
const markAllItemsOrderedMock = vi.fn<(id: number) => Promise<void>>()

vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({
    cancel: cancelMock,
    removeItem: removeItemMock,
    markAllItemsRequested: markAllItemsRequestedMock,
    markAllItemsOrdered: markAllItemsOrderedMock,
  }),
}))

// `confirm.require`'s conventional shape (message/header/icon/accept/reject
// props) is asserted directly on the mock call rather than through the real
// ConfirmDialog UI.
const confirmRequireMock = vi.fn<(option: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import OrderDetailView from '../OrderDetailView.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { makeOrderResponse, makeTestRouter } from '@/test-utils/factories'
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
    status: 'ordered',
    actions: ORDER_ACTIONS[overrides.status ?? 'ordered'],
    ...overrides,
  })
}

/**
 * Mirrors the real route, constraint included, so the view reads its id the
 * same way it does in the app.
 */
function makeRouter() {
  return makeTestRouter([
    { path: '/procurement/orders/:id(\\d+)', name: 'OrderDetail', component: OrderDetailView },
  ])
}

async function mountView() {
  const router = makeRouter()
  await router.push('/procurement/orders/42')
  await router.isReady()

  const wrapper = mountWithApp(OrderDetailView, {
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
      stubs: {
        OrderItemsTable: true,
        OrderFilesSection: true,
        OrderItemCreateForm: true,
        DeliverItemDialog: true,
        DeliveryHistoryDialog: true,
        DeliverAllDialog: true,
        MoveOrderItemDialog: true,
        OrderFieldEditDialog: true,
        OrderMailPostSendDialog: true,
        MailComposeDialog: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

function axiosError(status: number): unknown {
  return { isAxiosError: true, response: { status } }
}

/**
 * Puts the toolbar into its compact (tablet/phone) layout. The view's
 * `useMediaQuery` reads `matches` off whatever the global matchMedia stub
 * returns, so answering true for exactly its below-desktop query, and
 * nothing else since OpenVue components ask about their own breakpoints too,
 * is all it takes. Returns the restore function; call it in `finally`.
 */
function stubCompactScreen(): () => void {
  const original = window.matchMedia
  const compactQuery = `(max-width: ${constants.minWidthDesktop - 1}px)`
  vi.stubGlobal(
    'matchMedia',
    vi.fn<(query: string) => unknown>().mockImplementation((query: string) => ({
      ...(original(query) as object),
      matches: query === compactQuery,
    })),
  )
  return () => vi.stubGlobal('matchMedia', original)
}

function buttonLabels(wrapper: { findAll(selector: string): { text(): string }[] }): string[] {
  return wrapper.findAll('button').map((b) => b.text())
}

describe('OrderDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getOrderMock.mockReset()
    cancelMock.mockReset().mockResolvedValue(undefined)
    removeItemMock.mockReset().mockResolvedValue(undefined)
    markAllItemsRequestedMock.mockReset().mockResolvedValue(undefined)
    markAllItemsOrderedMock.mockReset().mockResolvedValue(undefined)
    confirmRequireMock.mockReset()
    filesById = {}
  })

  it('shows the order identity once loaded', async () => {
    getOrderMock.mockResolvedValue(makeOrder())

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('ORD-42')
    expect(wrapper.text()).toContain('ACME Supplies')
    // No tabs to switch between; the items table is always the content.
    expect(wrapper.findComponent({ name: 'OrderItemsTable' }).exists()).toBe(true)
  })

  it('shows expected delivery until an actual delivery date lands, then switches', async () => {
    getOrderMock.mockResolvedValue(
      makeOrder({ status: 'ordered', expected_delivery_date: '2026-03-01', delivery_date: null }),
    )
    const expected = await mountView()
    expect(expected.text()).toContain('2026-03-01')

    getOrderMock.mockResolvedValue(
      makeOrder({
        status: 'partially_delivered',
        expected_delivery_date: '2026-03-01',
        delivery_date: '2026-02-20T10:00:00Z',
      }),
    )
    const delivered = await mountView()
    expect(delivered.text()).toContain('2026-02-20')
  })

  it('shows the order note in its own side card, with a placeholder when unset', async () => {
    getOrderMock.mockResolvedValue(makeOrder({ note: 'Call before delivery' }))
    const withNote = await mountView()
    expect(withNote.find('.note-panel').exists()).toBe(true)
    expect(withNote.find('.note-text').text()).toBe('Call before delivery')

    getOrderMock.mockResolvedValue(makeOrder({ note: null }))
    const withoutNote = await mountView()
    expect(withoutNote.find('.note-text').exists()).toBe(false)
    expect(withoutNote.find('.note-empty').text()).toBe('No note set')
  })

  it('falls back to explicit placeholder text when delivery date and storage place are unset', async () => {
    getOrderMock.mockResolvedValue(makeOrder({ expected_delivery_date: null, delivery_date: null }))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('No delivery date set')
    expect(wrapper.text()).toContain('No storage place set')
  })

  describe('invoice missing hint', () => {
    async function mountWithStorage() {
      const wrapper = await mountView()
      // mountView installs its own pinia; the host store must be flipped on
      // that instance, after the mount.
      useHostStore().storageEnabled = true
      await nextTick()
      return wrapper
    }

    it('shows the hint for a delivered order without any invoice file', async () => {
      getOrderMock.mockResolvedValue(makeOrder({ status: 'delivered' }))

      const wrapper = await mountWithStorage()

      expect(wrapper.find('.invoice-missing').exists()).toBe(true)
      expect(wrapper.text()).toContain('Invoice missing')
    })

    it('hides the hint once an invoice file is attached', async () => {
      filesById[42] = [{ id: 1, order_id: 42, category: 'invoice' }]
      getOrderMock.mockResolvedValue(makeOrder({ status: 'delivered' }))

      const wrapper = await mountWithStorage()

      expect(wrapper.find('.invoice-missing').exists()).toBe(false)
    })

    it('does not nag an order that is not delivered yet', async () => {
      getOrderMock.mockResolvedValue(makeOrder({ status: 'ordered' }))

      const wrapper = await mountWithStorage()

      expect(wrapper.find('.invoice-missing').exists()).toBe(false)
    })

    it('stays silent when file storage is disabled on the host', async () => {
      getOrderMock.mockResolvedValue(makeOrder({ status: 'delivered' }))

      const wrapper = await mountView()

      expect(wrapper.find('.invoice-missing').exists()).toBe(false)
    })
  })

  it('shows the not-found state for an order that does not exist', async () => {
    getOrderMock.mockRejectedValue(axiosError(404))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('does not exist')
    expect(wrapper.findComponent({ name: 'OrderItemsTable' }).exists()).toBe(false)
  })

  it('distinguishes a failed load from a missing order', async () => {
    getOrderMock.mockRejectedValue(axiosError(500))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('could not be loaded')
    expect(wrapper.text()).not.toContain('does not exist')
  })

  it('offers the order-level actions in the toolbar rather than a context menu', async () => {
    getOrderMock.mockResolvedValue(makeOrder())

    const wrapper = await mountView()

    const labels = wrapper.findAll('button').map((b) => b.text())
    expect(labels.join(' ')).toContain('Mark All as Ordered')
    expect(labels.join(' ')).toContain('Cancel Order')
    expect(wrapper.findComponent({ name: 'ContextMenu' }).exists()).toBe(false)
  })

  it('lays the edit fields out as their own toolbar buttons on a desktop-width screen', async () => {
    getOrderMock.mockResolvedValue(makeOrder())

    const wrapper = await mountView()

    const labels = buttonLabels(wrapper)
    expect(labels).toContain('Supplier')
    expect(labels).toContain('Expected Delivery Date')
    expect(labels).toContain('Storage Place')
    expect(labels).toContain('Note')
    expect(labels).toContain('Request Mail')
    expect(labels).toContain('Order Mail')
    // No collapsed menu buttons at this width.
    expect(labels).not.toContain('Edit Order')
    expect(labels).not.toContain('Mark All')
    expect(labels).not.toContain('Mail')
  })

  it('collapses the edit, mark-all and mail actions into menu buttons below the desktop breakpoint', async () => {
    const restore = stubCompactScreen()
    try {
      getOrderMock.mockResolvedValue(
        makeOrder({
          items: [{ id: 1, status: 'requested', actions: ['mark_ordered'] } as OrderItemResponse],
        }),
      )

      const wrapper = await mountView()

      const labels = buttonLabels(wrapper)
      expect(labels).toContain('Edit Order')
      expect(labels).toContain('Mark All')
      expect(labels).toContain('Mail')
      expect(labels).not.toContain('Storage Place')
      expect(labels).not.toContain('Mark All as Ordered')
      expect(labels).not.toContain('Request Mail')
      // Only those three groups collapse; the rest of the bar is unchanged.
      expect(labels).toContain('Add Item')
      expect(labels).toContain('Cancel Order')

      // The menu behind "Mark All" carries the same actions and wiring the
      // desktop buttons have.
      const markAllButton = wrapper.findAll('button').find((b) => b.text() === 'Mark All')
      await markAllButton!.trigger('click')
      await flushPromises()

      const markOrdered = Array.from(document.body.querySelectorAll('[data-testid="mark-all-menu-item"]')).find(
        (el) => el.textContent?.trim() === 'Mark All as Ordered',
      )
      expect(markOrdered).toBeTruthy()
      markOrdered!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await flushPromises()

      expect(markAllItemsOrderedMock).toHaveBeenCalledWith(42)
    } finally {
      restore()
    }
  })

  it('confirms before canceling the order, and confirming calls the same store action', async () => {
    getOrderMock.mockResolvedValue(makeOrder({ status: 'ordered' }))

    const wrapper = await mountView()

    const cancelButton = wrapper.findAll('button').find((b) => b.text() === 'Cancel Order')
    expect(cancelButton).toBeTruthy()
    await cancelButton!.trigger('click')

    expect(cancelMock).not.toHaveBeenCalled()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as {
      message: string
      header: string
      acceptProps: { label: string; severity: string }
      rejectProps: { label: string; severity: string }
      accept: () => Promise<void>
    }
    expect(options.header).toBe('Cancel Order')
    expect(options.acceptProps).toEqual({ label: 'Cancel Order', severity: 'danger' })
    expect(options.rejectProps).toEqual({ label: 'Cancel', severity: 'secondary' })

    await options.accept()

    expect(cancelMock).toHaveBeenCalledWith(42, 0)
  })

  it('offers to notify the supplier with a second confirm once the cancel succeeds', async () => {
    getOrderMock.mockResolvedValue(makeOrder({ status: 'ordered' }))

    const wrapper = await mountView()

    const cancelButton = wrapper.findAll('button').find((b) => b.text() === 'Cancel Order')
    await cancelButton!.trigger('click')

    const cancelOptions = confirmRequireMock.mock.calls[0]![0] as { accept: () => Promise<void> }
    await cancelOptions.accept()
    await flushPromises()

    // A second, independent confirm.require() call, not folded into the
    // cancel one, offering to compose the cancellation mail. See
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

  it('does not offer canceling once the order is past the cancelable statuses', async () => {
    getOrderMock.mockResolvedValue(makeOrder({ status: 'delivered' }))

    const wrapper = await mountView()

    const cancelButton = wrapper.findAll('button').find((b) => b.text() === 'Cancel Order')
    expect(cancelButton?.attributes('disabled')).toBeDefined()
  })

  it('confirms before removing an item, and confirming calls the same store action', async () => {
    getOrderMock.mockResolvedValue(makeOrder())

    const wrapper = await mountView()

    const table = wrapper.findComponent({ name: 'OrderItemsTable' })
    const item = { id: 5, edit_version: 3 } as OrderItemResponse
    table.vm.$emit('remove', 42, item)

    expect(removeItemMock).not.toHaveBeenCalled()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0] as {
      header: string
      acceptProps: { label: string; severity: string }
      rejectProps: { label: string; severity: string }
      accept: () => Promise<void>
    }
    expect(options.header).toBe('Remove Item')
    expect(options.acceptProps).toEqual({ label: 'Remove Item', severity: 'danger' })
    expect(options.rejectProps).toEqual({ label: 'Cancel', severity: 'secondary' })

    await options.accept()

    expect(removeItemMock).toHaveBeenCalledWith(42, 5, 3)
  })
})
