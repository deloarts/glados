import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'

const deliverAllItemsMock = vi.fn<(...args: unknown[]) => Promise<number>>()
const getMock = vi.fn<(url: string) => Promise<unknown>>()
const toastInfoMock = vi.fn<(summary: string, detail?: string) => void>()

vi.mock('@/core/composables/useAppToast', () => ({
  useAppToast: () => ({
    info: toastInfoMock,
    success: vi.fn<() => void>(),
    warn: vi.fn<() => void>(),
    error: vi.fn<() => void>(),
  }),
}))

vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({
    deliverAllItems: deliverAllItemsMock,
  }),
}))

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
  },
}))

import DeliverAllDialog from '../DeliverAllDialog.vue'
import type { OrderItemResponse, OrderResponse } from '../../types/ordersResponse'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

// The backend offers a delivery on an ordered or partially delivered line of
// an order that is not canceled.
function deliverableActions(status: OrderItemResponse['status']): LifecycleAction[] {
  return status === 'ordered' || status === 'partially_delivered' ? ['deliver'] : []
}

function makeItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return makeOrderItemResponse({
    actions: deliverableActions(overrides.status ?? 'ordered'),
    status: 'ordered',
    quantity_rejected: 0,
    quantity_rejected_lost: 0,
    price: null,
    ...overrides,
  })
}

function makeOrder(items: OrderItemResponse[]): OrderResponse {
  return makeOrderResponse({ id: 99, status: 'ordered', items })
}

interface LineRejectState {
  show: boolean
  quantity: number | null
  reason: string | null
  note: string
  outcome: string | null
  createReplacement: boolean
}

interface DialogVm {
  storagePlace: string
  loadingItems: boolean
  items: OrderItemResponse[]
  eligibleItems: OrderItemResponse[]
  lineState(itemId: number): LineRejectState
  isMadeLine(item: OrderItemResponse): boolean
  canSubmit: boolean
}

function mockOrder(order: OrderResponse): void {
  getMock.mockImplementation((url: string) => {
    if (url === `/orders/${order.id}`) return Promise.resolve({ data: order })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

async function mountDialog(orderId: number) {
  const wrapper = mountWithApp(DeliverAllDialog, {
    attachTo: document.body,
    props: { visible: false, orderId },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await flushPromises()
  return wrapper
}

async function clickDeliverAll(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  await buttons.at(-1)!.trigger('click')
  await flushPromises()
}

describe('DeliverAllDialog', () => {
  beforeEach(() => {
    deliverAllItemsMock.mockReset()
    deliverAllItemsMock.mockResolvedValue(0)
    getMock.mockReset()
    toastInfoMock.mockReset()
  })

  it('says how many lines were left out when the backend skipped some', async () => {
    deliverAllItemsMock.mockResolvedValue(2)
    mockOrder(makeOrder([makeItem({ id: 1 })]))

    const wrapper = await mountDialog(99)
    await clickDeliverAll(wrapper)

    expect(toastInfoMock).toHaveBeenCalledTimes(1)
    expect(toastInfoMock.mock.calls[0]![1]).toContain('2')

    wrapper.unmount()
  })

  it('says nothing when no line was left out', async () => {
    mockOrder(makeOrder([makeItem({ id: 1 })]))

    const wrapper = await mountDialog(99)
    await clickDeliverAll(wrapper)

    expect(toastInfoMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('loads the order and lists only the ordered and partially delivered lines', async () => {
    const order = makeOrder([
      makeItem({ id: 1, status: 'pending' }),
      makeItem({ id: 2, status: 'requested' }),
      makeItem({ id: 3, status: 'ordered' }),
      makeItem({ id: 4, status: 'partially_delivered' }),
      makeItem({ id: 5, status: 'delivered' }),
      makeItem({ id: 6, status: 'canceled' }),
    ])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.eligibleItems.map((i) => i.id)).toEqual([3, 4])

    wrapper.unmount()
  })

  it('lists no line when the order is canceled', async () => {
    const order: OrderResponse = {
      // A canceled order's lines offer no delivery.
      ...makeOrder([
        makeItem({ id: 1, status: 'partially_delivered', quantity_delivered: 1, actions: [] }),
        makeItem({ id: 2, status: 'ordered', actions: [] }),
      ]),
      status: 'canceled',
    }
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.eligibleItems).toEqual([])
    expect(document.body.querySelector('.reject-toggle')).toBeNull()

    wrapper.unmount()
  })

  it('starts every line with its reject block collapsed', async () => {
    const order = makeOrder([makeItem({ id: 1 })])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.lineState(1).show).toBe(false)
    expect(document.body.querySelector('.reject-block')).toBeNull()

    wrapper.unmount()
  })

  it('toggles a line reject block open by clicking its toggle row', async () => {
    const order = makeOrder([makeItem({ id: 1 })])
    mockOrder(order)

    const wrapper = await mountDialog(99)

    await new DOMWrapper(document.body.querySelector('.reject-toggle')!).trigger('click')
    expect(document.body.querySelector('.reject-block')).not.toBeNull()

    wrapper.unmount()
  })

  it('blocks submit when a line rejection is missing its reason or outcome', async () => {
    const order = makeOrder([makeItem({ id: 1, quantity: 4, quantity_delivered: 0 })])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    vm.lineState(1).quantity = 1
    await flushPromises()
    expect(vm.canSubmit).toBe(false)

    vm.lineState(1).reason = 'supplier_damage'
    vm.lineState(1).outcome = 'redeliver'
    await flushPromises()
    expect(vm.canSubmit).toBe(true)

    wrapper.unmount()
  })

  it('blocks submit when a line rejection exceeds its remaining quantity', async () => {
    const order = makeOrder([makeItem({ id: 1, quantity: 4, quantity_delivered: 0 })])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    vm.lineState(1).quantity = 5
    vm.lineState(1).reason = 'supplier_damage'
    vm.lineState(1).outcome = 'redeliver'
    await flushPromises()

    expect(vm.canSubmit).toBe(false)

    wrapper.unmount()
  })

  it('submits with no rejections when no line has anything entered', async () => {
    const order = makeOrder([makeItem({ id: 1 }), makeItem({ id: 2 })])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    await clickDeliverAll(wrapper)

    expect(deliverAllItemsMock).toHaveBeenCalledWith(99, undefined, undefined, undefined)

    wrapper.unmount()
  })

  it('submits one rejection entry per rejected line, leaving other lines untouched', async () => {
    const order = makeOrder([
      makeItem({ id: 1, quantity: 4, quantity_delivered: 0, line_type: 'BOUGHT' }),
      makeItem({ id: 2, quantity: 2, quantity_delivered: 0, line_type: 'MADE' }),
    ])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    vm.lineState(2).quantity = 1
    vm.lineState(2).reason = 'supplier_damage'
    vm.lineState(2).note = 'Dented'
    vm.lineState(2).outcome = 'lost'
    vm.lineState(2).createReplacement = false
    await flushPromises()

    await clickDeliverAll(wrapper)

    expect(deliverAllItemsMock).toHaveBeenCalledWith(
      99,
      undefined,
      [
        {
          order_item_id: 2,
          quantity_rejected: 1,
          rejection_reason: 'supplier_damage',
          rejection_note: 'Dented',
          rejection_outcome: 'lost',
          create_replacement: false,
        },
      ],
      undefined,
    )

    wrapper.unmount()
  })

  it('shows the create-replacement checkbox only for a MADE line with outcome lost', async () => {
    const order = makeOrder([
      makeItem({ id: 1, line_type: 'BOUGHT' }),
      makeItem({ id: 2, line_type: 'MADE' }),
    ])
    mockOrder(order)

    const wrapper = await mountDialog(99)
    const vm = wrapper.vm as unknown as DialogVm

    expect(vm.isMadeLine(order.items[0]!)).toBe(false)
    expect(vm.isMadeLine(order.items[1]!)).toBe(true)

    wrapper.unmount()
  })
})
