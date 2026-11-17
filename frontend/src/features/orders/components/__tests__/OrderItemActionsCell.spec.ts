import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse } from '@/test-utils/factories'
import OrderItemActionsCell from '../OrderItemActionsCell.vue'
import type { OrderItemPermissions } from '../../composables/useOrderItemActions'
import type { OrderItemResponse } from '../../types/ordersResponse'

const ALL: OrderItemPermissions = { canWrite: true, canManage: true, canReceiveDeliveries: true }
const NONE: OrderItemPermissions = { canWrite: false, canManage: false, canReceiveDeliveries: false }

function mountCell(item: OrderItemResponse, permissions: OrderItemPermissions) {
  return mountWithApp(OrderItemActionsCell, {
    props: {
      item,
      permissions,
      isPage: true,
      editing: false,
      saving: false,
      markingOrdered: false,
      busy: false,
    },
    global: { directives: { tooltip: Tooltip } },
  })
}

function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)
    ?.$_ptooltipValue
}

describe('OrderItemActionsCell', () => {
  it('shows the inline actions the line offers, enabled with the permissions', () => {
    const item = makeOrderItemResponse({
      status: 'ordered',
      actions: ['deliver', 'mark_ordered', 'edit'],
    })
    const wrapper = mountCell(item, ALL)

    for (const label of ['Mark Delivered', 'Mark as Ordered', 'Edit Item']) {
      expect(wrapper.get(`button[aria-label="${label}"]`).attributes('disabled')).toBeUndefined()
    }
  })

  it('shows the offered actions disabled with the missing permission without the rights', () => {
    const item = makeOrderItemResponse({
      status: 'ordered',
      actions: ['deliver', 'mark_ordered', 'edit'],
    })
    const wrapper = mountCell(item, NONE)

    const deliver = wrapper.get('button[aria-label="Mark Delivered"]')
    expect(deliver.attributes('disabled')).toBeDefined()
    expect(tooltipOf(deliver)).toBe('This needs the permission Receive Deliveries.')
    const markOrdered = wrapper.get('button[aria-label="Mark as Ordered"]')
    expect(markOrdered.attributes('disabled')).toBeDefined()
    expect(tooltipOf(markOrdered)).toBe('This needs the permission Write Orders.')
    const edit = wrapper.get('button[aria-label="Edit Item"]')
    expect(edit.attributes('disabled')).toBeDefined()
    expect(tooltipOf(edit)).toBe('This needs the permission Write Orders.')
  })

  it('names manage:orders on Edit of a delivered line for a writer', () => {
    const item = makeOrderItemResponse({
      status: 'delivered',
      actions: [],
      blocked_actions: { edit: 'manage:orders' },
    })
    const wrapper = mountCell(item, { ...NONE, canWrite: true })

    const edit = wrapper.get('button[aria-label="Edit Item"]')
    expect(edit.attributes('disabled')).toBeDefined()
    expect(tooltipOf(edit)).toBe('This needs the permission Manage Orders.')
  })

  it('hides the actions the line does not offer', () => {
    const item = makeOrderItemResponse({ status: 'canceled', actions: [] })
    const wrapper = mountCell(item, ALL)

    expect(wrapper.find('button[aria-label="Mark Delivered"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Mark as Ordered"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Edit Item"]').exists()).toBe(false)
  })
})
