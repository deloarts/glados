import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

const updateItemMock = vi.fn<(...args: unknown[]) => Promise<void>>()

vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({
    updateItem: updateItemMock,
    markItemOrdered: vi.fn<() => Promise<void>>(),
    markItemRequested: vi.fn<() => Promise<void>>(),
    markItemReadyForPickup: vi.fn<() => Promise<void>>(),
  }),
}))

import OrderItemsTable from '../OrderItemsTable.vue'
import type { OrderItemResponse, OrderResponse } from '../../types/ordersResponse'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function makeOrder(items: OrderItemResponse[]): OrderResponse {
  return makeOrderResponse({ id: 99, items })
}

function mountTable(
  order: OrderResponse,
  variant: 'page' | 'embedded' = 'embedded',
  extraProps: Record<string, unknown> = {},
) {
  return mountWithApp(OrderItemsTable, {
    props: { order, canWrite: true, canManage: true, variant, ...extraProps },
    global: {
      directives: { tooltip: Tooltip },
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
        BoughtItemThumbnailCell: true,
        MadeItemThumbnailCell: true,
        BoughtItemDetailDialog: true,
        MadeItemDetailDialog: true,
        ProjectSelect: true,
        OrderItemCellBought: true,
        OrderItemCellMade: true,
        OrderItemCellSource: true,
        OrderItemCellVirtual: true,
        OrderItemCellBoughtEdit: true,
        OrderItemCellMadeEdit: true,
        OrderItemCellSourceEdit: true,
        OrderItemCellVirtualEdit: true,
      },
    },
  })
}

describe('OrderItemsTable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    updateItemMock.mockReset()
    updateItemMock.mockResolvedValue(undefined)
  })

  it('renders one row per item', () => {
    const wrapper = mountTable(
      makeOrder([makeOrderItemResponse(), makeOrderItemResponse({ id: 2, position: 2 })]),
    )

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('shows the empty template for an order with no items', () => {
    const wrapper = mountTable(makeOrder([]))

    expect(wrapper.text()).toContain('No items in this order yet.')
  })

  it('shows a rejected-quantity note next to a line that has one', () => {
    const wrapper = mountTable(makeOrder([makeOrderItemResponse({ quantity_rejected: 1 })]))

    expect(wrapper.text()).toContain('1 rejected')
    expect(wrapper.text()).not.toContain('lost')
  })

  it('names the lost pieces in the same note as the rejected ones', () => {
    const wrapper = mountTable(
      makeOrder([makeOrderItemResponse({ quantity_rejected: 2, quantity_rejected_lost: 1 })]),
    )

    expect(wrapper.findAll('[data-testid="rejected-note"]').map((n) => n.text())).toEqual([
      '2 rejected, 1 lost',
    ])
  })

  it('shows neither note for a line with no rejection', () => {
    const wrapper = mountTable(makeOrder([makeOrderItemResponse()]))

    expect(wrapper.text()).not.toContain('rejected')
    expect(wrapper.text()).not.toContain('lost')
  })

  it('renders no net-total footer in either variant', () => {
    // The embedded table sits under a list row that shows the total, and
    // the page variant shows it in the detail view's info bar.
    const embedded = mountTable(makeOrder([makeOrderItemResponse()]), 'embedded')
    expect(embedded.find('.items-footer').exists()).toBe(false)

    const page = mountTable(makeOrder([makeOrderItemResponse()]), 'page')
    expect(page.find('.items-footer').exists()).toBe(false)
  })

  it('offers sorting only in the page variant', () => {
    const embedded = mountTable(makeOrder([makeOrderItemResponse()]), 'embedded')
    expect(embedded.find('th[data-p-sortable-column="true"]').exists()).toBe(false)

    const page = mountTable(makeOrder([makeOrderItemResponse()]), 'page')
    expect(page.find('th[data-p-sortable-column="true"]').exists()).toBe(true)
  })

  it('shows the actions column by default and hides it when showActions is false', () => {
    const order = makeOrder([makeOrderItemResponse()])

    const shown = mountTable(order, 'page')
    expect(shown.find('.item-actions-cell').exists()).toBe(true)

    const hidden = mountTable(order, 'page', { showActions: false })
    expect(hidden.find('.item-actions-cell').exists()).toBe(false)
  })

  it('brings the hidden actions column back while a row is being edited', async () => {
    // The actions cell is where the edit row's save/cancel buttons live;
    // hiding it during an edit would strand the row with no way to commit.
    const item = makeOrderItemResponse()
    const wrapper = mountTable(makeOrder([item]), 'page', { showActions: false })
    expect(wrapper.find('.item-actions-cell').exists()).toBe(false)

    const vm = wrapper.vm as unknown as {
      startEdit(item: OrderItemResponse): void
      cancelEdit(itemId: number): void
    }

    vm.startEdit(item)
    await flushPromises()
    expect(wrapper.find('.item-actions-cell').exists()).toBe(true)

    vm.cancelEdit(item.id)
    await flushPromises()
    expect(wrapper.find('.item-actions-cell').exists()).toBe(false)
  })

  it('converts price back to cents and omits unchanged fields when saving an edit', async () => {
    const item = makeOrderItemResponse()
    const wrapper = mountTable(makeOrder([item]))

    const vm = wrapper.vm as unknown as {
      startEdit(item: OrderItemResponse): void
      saveItemEdit(item: OrderItemResponse): Promise<void>
    }

    vm.startEdit(item)
    await flushPromises()
    await vm.saveItemEdit(item)

    expect(updateItemMock).toHaveBeenCalledTimes(1)
    const [orderId, itemId, payload] = updateItemMock.mock.calls[0] as [
      number,
      number,
      Record<string, unknown>,
    ]
    expect(orderId).toBe(99)
    expect(itemId).toBe(1)
    // Round-trips through euros in the input and back, unchanged.
    expect(payload.price).toBe(1250)
    // Nothing was touched, so neither the substitution nor the project-move
    // keys may appear. The API treats their presence as an instruction.
    expect(payload).not.toHaveProperty('bought_item_id')
    expect(payload).not.toHaveProperty('project_id')
    expect(payload).not.toHaveProperty('position')
    expect(payload).not.toHaveProperty('virtual_name')
  })

  it('surfaces a failed save instead of leaving the row silently unedited', async () => {
    updateItemMock.mockRejectedValue(new Error('nope'))
    const item = makeOrderItemResponse()
    const wrapper = mountTable(makeOrder([item]))

    const vm = wrapper.vm as unknown as {
      startEdit(item: OrderItemResponse): void
      saveItemEdit(item: OrderItemResponse): Promise<void>
    }

    vm.startEdit(item)
    await vm.saveItemEdit(item)
    await flushPromises()

    expect(wrapper.text()).toContain('Something went wrong')
  })
})

describe('OrderItemsTable page row filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const items = [
    makeOrderItemResponse({
      id: 1,
      position: 1,
      quantity: 4,
      price: 1250,
      item_article_name: 'Widget',
      item_order_code_1: 'OC-1',
      expected_delivery_date: '2026-03-05',
      expected_pickup_date: null,
      delivery_date: '2026-03-06T09:00:00Z',
      note: 'urgent please',
      storage_place: 'Shelf A',
    }),
    makeOrderItemResponse({
      id: 2,
      position: 2,
      quantity: 20,
      price: 99900,
      item_article_name: 'Gear',
      item_order_code_1: 'GR-77',
      item_specification: 'M8 steel',
      expected_delivery_date: '2026-04-10',
      expected_pickup_date: '2026-04-12',
      delivery_date: null,
      note: null,
      storage_place: 'Shelf B',
    }),
    makeOrderItemResponse({
      id: 3,
      position: 3,
      quantity: 1,
      price: null,
      item_article_name: 'Bolt',
      item_order_code_1: 'BL-3',
      expected_delivery_date: null,
      expected_pickup_date: '2026-05-01',
      delivery_date: null,
      note: 'second batch',
      storage_place: null,
    }),
  ]

  type FilterVm = {
    filters: Record<string, { value: unknown; matchMode: string }>
    clearFilters(): void
    hasActiveFilters: boolean
  }

  function positions(wrapper: ReturnType<typeof mountTable>): number[] {
    const vm = wrapper.findComponent({ name: 'DataTable' }).vm as unknown as {
      processedData: OrderItemResponse[]
    }
    return vm.processedData.map((item) => item.position)
  }

  async function setFilter(
    wrapper: ReturnType<typeof mountTable>,
    field: string,
    value: unknown,
  ): Promise<void> {
    const vm = wrapper.vm as unknown as FilterVm
    vm.filters = { ...vm.filters, [field]: { ...vm.filters[field]!, value } }
    await flushPromises()
  }

  it('narrows rows by item text typed into the filter row', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    expect(wrapper.findAll('tbody tr')).toHaveLength(3)

    await wrapper.find('input[aria-label="Filter by Item"]').setValue('gr-77')
    await flushPromises()

    expect(positions(wrapper)).toEqual([2])
    expect((wrapper.vm as unknown as FilterVm).hasActiveFilters).toBe(true)
  })

  it('matches the item filter against the specification too', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    await setFilter(wrapper, '_itemText', 'steel')
    expect(positions(wrapper)).toEqual([2])
  })

  it('narrows rows by a quantity range', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    await setFilter(wrapper, 'quantity', [2, 10])
    expect(positions(wrapper)).toEqual([1])
  })

  it('narrows rows by a price range in currency units rather than cents', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    await setFilter(wrapper, '_priceMajor', [10, 20])
    expect(positions(wrapper)).toEqual([1])
    await setFilter(wrapper, '_priceMajor', [500, null])
    expect(positions(wrapper)).toEqual([2])
  })

  it('narrows rows by expected delivery, expected pickup and delivery date ranges', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    await setFilter(wrapper, 'expected_delivery_date', [new Date(2026, 3, 1), new Date(2026, 3, 30)])
    expect(positions(wrapper)).toEqual([2])

    await setFilter(wrapper, 'expected_delivery_date', null)
    await setFilter(wrapper, 'expected_pickup_date', [new Date(2026, 4, 1), null])
    expect(positions(wrapper)).toEqual([3])

    await setFilter(wrapper, 'expected_pickup_date', null)
    await setFilter(wrapper, 'delivery_date', [new Date(2026, 2, 6), new Date(2026, 2, 6)])
    expect(positions(wrapper)).toEqual([1])
  })

  it('narrows rows by note and storage place', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    await setFilter(wrapper, 'note', 'batch')
    expect(positions(wrapper)).toEqual([3])

    await setFilter(wrapper, 'note', null)
    await setFilter(wrapper, 'storage_place', 'shelf b')
    expect(positions(wrapper)).toEqual([2])
  })

  it('shows every row again after clearFilters', async () => {
    const wrapper = mountTable(makeOrder(items), 'page')
    await setFilter(wrapper, 'storage_place', 'shelf')
    expect(positions(wrapper)).toEqual([1, 2])

    const vm = wrapper.vm as unknown as FilterVm
    vm.clearFilters()
    await flushPromises()

    expect(positions(wrapper)).toEqual([1, 2, 3])
    expect(vm.hasActiveFilters).toBe(false)
  })

  it('renders no filter row in the embedded variant', () => {
    const wrapper = mountTable(makeOrder(items), 'embedded')
    expect(wrapper.find('input[aria-label="Filter by Item"]').exists()).toBe(false)
    expect(wrapper.findAll('tbody tr')).toHaveLength(3)
  })
})
