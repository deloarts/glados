import { describe, it, expect } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { MenuItem } from 'openvue/menuitem'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { OrderResponse } from '../../types/ordersResponse'

import { useOrderEditFields } from '../useOrderEditFields'

// The edit menu gates each field on its own: the header fields on the
// order's edit action, the supplier order numbers on theirs, which a user
// with only write:orders keeps after the order went out.

function menuFor(order: OrderResponse, permissions: string[]): MenuItem[] {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  let items: MenuItem[] = []
  mountWithApp(
    defineComponent({
      setup() {
        items = useOrderEditFields().menuItems(order)
        return () => h('div')
      },
    }),
    { pinia },
  )
  return items
}

// By icon, since the labels follow the test locale.
function byIcon(items: MenuItem[], icon: string): MenuItem {
  return items.find((item) => item.icon === icon)!
}

const NUMBERS = 'mdi mdi-pound-box-outline'
const SUPPLIER = 'mdi mdi-domain'
const NOTE = 'mdi mdi-note-text-outline'

describe('useOrderEditFields', () => {
  it('leaves the numbers open on an ordered order whose header needs manage:orders', () => {
    const order = makeOrderResponse({
      status: 'ordered',
      actions: ['edit_supplier_order_numbers'],
      blocked_actions: { edit: 'manage:orders' },
    })

    const items = menuFor(order, ['write:orders'])

    const numbers = byIcon(items, NUMBERS)
    expect(numbers.disabled).toBe(false)
    expect(numbers.title).toBeUndefined()
    const supplier = byIcon(items, SUPPLIER)
    expect(supplier.disabled).toBe(true)
    expect(supplier.title).toBeTruthy()
  })

  it('disables the numbers on a delivered order and says why', () => {
    const order = makeOrderResponse({ status: 'delivered', actions: ['edit'] })

    const items = menuFor(order, ['write:orders', 'manage:orders'])

    const numbers = byIcon(items, NUMBERS)
    expect(numbers.disabled).toBe(true)
    expect(numbers.title).toBeTruthy()
    expect(byIcon(items, NOTE).disabled).toBe(false)
  })

  it('disables every field for a user without write:orders', () => {
    const order = makeOrderResponse({ actions: ['edit', 'edit_supplier_order_numbers'] })

    const items = menuFor(order, [])

    expect(items.every((item) => item.disabled === true)).toBe(true)
  })
})
