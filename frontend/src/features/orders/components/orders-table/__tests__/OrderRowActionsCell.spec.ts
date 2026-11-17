import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'
import OrderRowActionsCell from '../OrderRowActionsCell.vue'
import type { OrderItemResponse, OrderResponse } from '../../../types/ordersResponse'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

// What the backend offers on a line in each status, on an order that is not
// canceled (the order item intent table).
const LINE_ACTIONS: Record<OrderItemResponse['status'], LifecycleAction[]> = {
  pending: ['mark_requested', 'mark_ordered', 'cancel', 'edit_quantity', 'move', 'remove'],
  requested: ['mark_ordered', 'cancel', 'edit_quantity', 'move', 'remove'],
  ordered: ['deliver', 'cancel', 'edit_quantity', 'move'],
  partially_delivered: ['deliver', 'correct_delivery', 'close_short'],
  delivered: ['correct_delivery'],
  canceled: [],
}

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

function makeItem(status: OrderItemResponse['status']): OrderItemResponse {
  return { status, actions: LINE_ACTIONS[status] } as OrderItemResponse
}

// OrdersTable.vue's "Actions" column body. Each button's
// visibility depends on a mix of permission flags and the order's own item
// statuses, none of which OrdersTable.spec.ts exercises beyond the Cancel
// button.

function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)
    ?.$_ptooltipValue
}

function makeOrder(overrides: Partial<OrderResponse> = {}): OrderResponse {
  const status = overrides.status ?? 'ordered'
  return makeOrderResponse({ status, actions: ORDER_ACTIONS[status], ...overrides })
}

function mountCell(order: OrderResponse, permissions: Record<string, boolean> = {}) {
  return mountWithApp(OrderRowActionsCell, {
    props: {
      order,
      canWrite: permissions.canWrite ?? true,
      canManage: permissions.canManage ?? true,
      canReceiveDeliveries: permissions.canReceiveDeliveries ?? true,
      markingAllRequestedPending: false,
      markingAllOrderedPending: false,
    },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('OrderRowActionsCell', () => {
  it('shows Cancel only when the order offers it, disabled without canWrite', async () => {
    const cancelable = mountCell(makeOrder({ status: 'ordered' }))
    expect(cancelable.find('button[aria-label="Cancel Order"]').exists()).toBe(true)

    const delivered = mountCell(makeOrder({ status: 'delivered' }))
    expect(delivered.find('button[aria-label="Cancel Order"]').exists()).toBe(false)

    // Past requested, the backend offers cancel only to a manager of orders.
    const notOffered = mountCell(makeOrder({ status: 'ordered', actions: ['deliver'] }))
    expect(notOffered.find('button[aria-label="Cancel Order"]').exists()).toBe(false)

    const noWrite = mountCell(makeOrder({ status: 'ordered' }), { canWrite: false })
    const cancel = noWrite.get('button[aria-label="Cancel Order"]')
    expect(cancel.attributes('disabled')).toBeDefined()
    expect(tooltipOf(cancel)).toBe('This needs the permission Write Orders.')
  })

  it('shows a cancel the order blocks disabled, naming the permission it lacks', () => {
    // Past requested, a writer without manage:orders may not cancel; the
    // backend reports the cancel as blocked rather than leaving it out.
    const wrapper = mountCell(
      makeOrder({
        status: 'ordered',
        actions: ['deliver'],
        blocked_actions: { cancel: 'manage:orders' },
      }),
      { canManage: false },
    )

    const cancel = wrapper.get('button[aria-label="Cancel Order"]')
    expect(cancel.attributes('disabled')).toBeDefined()
    expect(tooltipOf(cancel)).toBe('This needs the permission Manage Orders.')
  })

  it('shows a mark-all the lines block disabled, naming the permission they lack', () => {
    const blockedLine = {
      status: 'pending',
      actions: [],
      blocked_actions: { mark_requested: 'manage:orders', mark_ordered: 'manage:orders' },
    } as unknown as OrderItemResponse
    const wrapper = mountCell(makeOrder({ status: 'ordered', items: [blockedLine] }), {
      canManage: false,
    })

    const markAll = wrapper.get('[data-testid="mark-all-requested"]')
    expect(markAll.attributes('disabled')).toBeDefined()
    expect(tooltipOf(markAll)).toBe('This needs the permission Manage Orders.')
  })

  it('shows "mark all requested" only when a pending item exists, disabled without canWrite', () => {
    const withPending = mountCell(makeOrder({ items: [makeItem('pending')] }))
    expect(withPending.find('[data-testid="mark-all-requested"]').exists()).toBe(true)

    const withoutPending = mountCell(makeOrder({ items: [makeItem('delivered')] }))
    expect(withoutPending.find('[data-testid="mark-all-requested"]').exists()).toBe(false)

    const noWrite = mountCell(makeOrder({ items: [makeItem('pending')] }), { canWrite: false })
    const markAll = noWrite.get('[data-testid="mark-all-requested"]')
    expect(markAll.attributes('disabled')).toBeDefined()
    expect(tooltipOf(markAll)).toBe('This needs the permission Write Orders.')
  })

  it('shows "deliver all" only when an undelivered, non-pending/requested item exists, disabled without canReceiveDeliveries', () => {
    const deliverable = mountCell(makeOrder({ items: [makeItem('ordered')] }))
    expect(deliverable.find('[data-testid="deliver-all"]').exists()).toBe(true)

    const notDeliverable = mountCell(makeOrder({ items: [makeItem('requested')] }))
    expect(notDeliverable.find('[data-testid="deliver-all"]').exists()).toBe(false)

    const noReceive = mountCell(makeOrder({ items: [makeItem('ordered')] }), {
      canReceiveDeliveries: false,
    })
    const deliverAll = noReceive.get('[data-testid="deliver-all"]')
    expect(deliverAll.attributes('disabled')).toBeDefined()
    expect(tooltipOf(deliverAll)).toBe('This needs the permission Receive Deliveries.')
  })

  it('shows Edit and Add Item disabled with the missing permission without canWrite', () => {
    const wrapper = mountCell(makeOrder(), { canWrite: false })
    for (const label of ['Edit Order', 'Add Item']) {
      const button = wrapper.get(`button[aria-label="${label}"]`)
      expect(button.attributes('disabled')).toBeDefined()
      expect(tooltipOf(button)).toBe('This needs the permission Write Orders.')
    }
  })

  it('emits the order on cancel, edit (with the click event), and add-item', async () => {
    const order = makeOrder({ status: 'draft' })
    const wrapper = mountCell(order)

    await wrapper.find('button[aria-label="Cancel Order"]').trigger('click')
    expect(wrapper.emitted('cancel')?.[0]).toEqual([order])

    await wrapper.find('button[aria-label="Edit Order"]').trigger('click')
    const editEmit = wrapper.emitted('edit')?.[0]
    expect(editEmit?.[0]).toEqual(order)
    expect(editEmit?.[1]).toBeInstanceOf(Event)

    await wrapper.find('button[aria-label="Add Item"]').trigger('click')
    expect(wrapper.emitted('add-item')?.[0]).toEqual([order])
  })
})
