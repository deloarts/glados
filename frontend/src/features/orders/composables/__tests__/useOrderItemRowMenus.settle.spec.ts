import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

const cancelItemMock = vi.fn<(orderId: number, itemId: number) => Promise<void>>()
const closeItemShortMock = vi.fn<(orderId: number, itemId: number) => Promise<void>>()
const reopenItemMock =
  vi.fn<(orderId: number, itemId: number, version: number) => Promise<void>>()

vi.mock('../../stores/ordersStore', () => ({
  useOrdersStore: () => ({
    cancelItem: cancelItemMock,
    closeItemShort: closeItemShortMock,
    reopenItem: reopenItemMock,
    markItemOrdered: vi.fn<() => Promise<void>>(),
    markItemRequested: vi.fn<() => Promise<void>>(),
    markItemReadyForPickup: vi.fn<() => Promise<void>>(),
  }),
}))

import { useOrderItemRowMenus } from '../useOrderItemRowMenus'
import type { OrderItemResponse, OrderResponse } from '../../types/ordersResponse'

const t = i18n.global.t as (key: string, values?: Record<string, unknown>) => string

function line(id: number, actions: string[], overrides: Partial<OrderItemResponse> = {}) {
  return {
    id,
    public_id: `item-${id}`,
    status: 'ordered',
    actions,
    quantity: 10,
    quantity_delivered: 0,
    quantity_rejected_lost: 0,
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    delivery_records: [],
    edit_version: 2,
    ...overrides,
  } as OrderItemResponse
}

function mountMenus(permissions = { canWrite: true, canManage: false, canReceiveDeliveries: false }) {
  const updated = vi.fn<() => void>()
  let menus!: ReturnType<typeof useOrderItemRowMenus>
  const Host = defineComponent({
    setup() {
      menus = useOrderItemRowMenus(
        { order: { id: 7 } as OrderResponse, ...permissions },
        {
          edit: vi.fn<(item: OrderItemResponse) => void>(),
          move: vi.fn<(item: OrderItemResponse) => void>(),
          deliver: vi.fn<(item: OrderItemResponse) => void>(),
          viewHistory: vi.fn<(item: OrderItemResponse) => void>(),
          remove: vi.fn<(item: OrderItemResponse) => void>(),
          updated,
        },
      )
      return () => h('div')
    },
  })
  mountWithApp(Host)
  return { menus, updated }
}

function entry(menus: ReturnType<typeof useOrderItemRowMenus>, label: string) {
  const found = menus.contextMenuItems.value.find((item) => item.label === label)
  if (!found) throw new Error(`No menu entry ${label}`)
  return found
}

beforeEach(() => {
  cancelItemMock.mockReset().mockResolvedValue(undefined)
  closeItemShortMock.mockReset().mockResolvedValue(undefined)
  reopenItemMock.mockReset().mockResolvedValue(undefined)
})

describe('useOrderItemRowMenus, canceling and closing lines short', () => {
  it('offers cancel and close short only where the line offers them', () => {
    const { menus } = mountMenus()

    menus.contextMenuItem.value = line(1, ['deliver', 'cancel', 'move'])
    expect(entry(menus, t('orders.actions.cancelItem')).disabled).toBe(false)
    expect(entry(menus, t('orders.actions.closeShort')).disabled).toBe(true)
    expect(entry(menus, t('orders.actions.removeItem')).disabled).toBe(true)

    menus.contextMenuItem.value = line(2, ['deliver', 'close_short'], {
      status: 'partially_delivered',
    })
    expect(entry(menus, t('orders.actions.cancelItem')).disabled).toBe(true)
    expect(entry(menus, t('orders.actions.closeShort')).disabled).toBe(false)
  })

  it('offers neither to a user who cannot write orders', () => {
    const { menus } = mountMenus({ canWrite: false, canManage: false, canReceiveDeliveries: true })

    menus.contextMenuItem.value = line(1, ['cancel', 'close_short'])

    expect(entry(menus, t('orders.actions.cancelItem')).disabled).toBe(true)
    expect(entry(menus, t('orders.actions.closeShort')).disabled).toBe(true)
  })

  it('asks before canceling a line, then cancels it and reports the change', async () => {
    const { menus, updated } = mountMenus()
    menus.contextMenuItem.value = line(3, ['cancel'])

    entry(menus, t('orders.actions.cancelItem')).command?.({} as never)

    expect(menus.settleConfirmVisible.value).toBe(true)
    expect(menus.settleConfirm.value?.message).toBe(t('orders.actions.cancelItemConfirm'))
    expect(cancelItemMock).not.toHaveBeenCalled()

    await menus.confirmSettle()
    await flushPromises()

    expect(cancelItemMock).toHaveBeenCalledWith(7, 3, 2)
    expect(updated).toHaveBeenCalledTimes(1)
  })

  it('names what was received when asking before closing a line short', async () => {
    const { menus } = mountMenus()
    menus.contextMenuItem.value = line(4, ['close_short'], {
      status: 'partially_delivered',
      quantity_delivered: 6,
      quantity_rejected_lost: 1,
    })

    entry(menus, t('orders.actions.closeShort')).command?.({} as never)

    expect(menus.settleConfirm.value?.message).toBe(
      t('orders.actions.closeShortConfirm', { delivered: 7, quantity: 10 }),
    )
    await menus.confirmSettle()
    await flushPromises()
    expect(closeItemShortMock).toHaveBeenCalledWith(7, 4, 2)
  })

  it('keeps the table unchanged when the backend refuses', async () => {
    cancelItemMock.mockRejectedValue(new Error('409'))
    const { menus, updated } = mountMenus()
    menus.contextMenuItem.value = line(5, ['cancel'])

    entry(menus, t('orders.actions.cancelItem')).command?.({} as never)
    await menus.confirmSettle()
    await flushPromises()

    expect(updated).not.toHaveBeenCalled()
  })

  it('asks before reopening a line closed short, naming the quantity it gets back', async () => {
    const { menus, updated } = mountMenus()
    menus.contextMenuItem.value = line(6, ['reopen'], {
      status: 'delivered',
      quantity: 8,
      quantity_delivered: 8,
      closed_short_from: 10,
    })

    entry(menus, t('orders.actions.reopenItem')).command?.({} as never)

    expect(menus.settleConfirm.value?.message).toBe(
      t('orders.actions.reopenItemConfirm', { quantity: 10 }),
    )
    await menus.confirmSettle()
    await flushPromises()
    expect(reopenItemMock).toHaveBeenCalledWith(7, 6, 2)
    expect(updated).toHaveBeenCalledTimes(1)
  })

  it('offers reopen disabled to a line that is not closed short', () => {
    const { menus } = mountMenus()

    menus.contextMenuItem.value = line(7, ['correct_delivery'], { status: 'delivered' })

    expect(entry(menus, t('orders.actions.reopenItem')).disabled).toBe(true)
  })
})

describe('useOrderItemRowMenus, moving and delivering lines', () => {
  it('lets a writer without manage:orders move a line the line offers it on', () => {
    const { menus } = mountMenus()

    menus.contextMenuItem.value = line(1, ['deliver', 'move'], { status: 'pending' })
    expect(entry(menus, t('orders.actions.moveItem')).disabled).toBe(false)
  })

  it('names the missing permission on a deliverable line the user may not receive', () => {
    const { menus } = mountMenus()

    menus.contextMenuItem.value = line(1, ['deliver'])
    const deliver = entry(menus, t('orders.actions.deliver'))
    expect(deliver.disabled).toBe(true)
    expect(deliver.title).toBe('This needs the permission Receive Deliveries.')
  })
})
