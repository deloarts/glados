import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'

import LotManagePositionsDock from '../LotManagePositionsDock.vue'
import { lotActions, makeLot, makePosition } from '../../../__tests__/fixtures'
import type { LotResponse } from '../../../../types/productionLotsResponse'

function mountDock(lot: LotResponse, permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { is_systemuser: false, permissions } as never
  return mountWithApp(LotManagePositionsDock, {
    pinia,
    props: { lotId: lot.id, lot, canWriteOrders: permissions.includes(Permission.WRITE_ORDERS) },
    global: {
      directives: { tooltip: Tooltip },
      stubs: {
        LotManageOrdersPanel: true,
        LotManageProductionPanel: true,
        LotPositionAssignDialog: true,
        LotPositionAssignInternalDialog: true,
        LotPositionProvisionDialog: true,
        LotAppendPositionDialog: true,
      },
    },
  })
}

function button(wrapper: ReturnType<typeof mountDock>, testId: string) {
  return wrapper.find(`[data-testid="${testId}"]`)
}

const EVERYTHING = [
  Permission.WRITE_LOTS,
  Permission.WRITE_ORDERS,
  Permission.WRITE_PRODUCTION_ORDERS,
]

describe('LotManagePositionsDock', () => {
  it('offers a new position on a lot that offers structure edits', async () => {
    const wrapper = mountDock(makeLot([makePosition()]), EVERYTHING)
    await flushPromises()

    expect(button(wrapper, 'append-position').attributes('disabled')).toBeUndefined()
  })

  it('offers no new position on a scrapped lot', async () => {
    const lot = { ...makeLot([makePosition()]), status: 'scrapped', actions: lotActions('scrapped') }
    const wrapper = mountDock(lot as LotResponse, EVERYTHING)
    await flushPromises()

    expect(button(wrapper, 'append-position').attributes('disabled')).toBeDefined()
  })

  it('shows each position action the position offers', async () => {
    const lot = makeLot([
      makePosition({ id: 1 }),
      makePosition({
        id: 2,
        sequence: 2,
        kind: 'external',
        order_item_id: 40,
        order_item_status: 'pending',
        quantity_remaining: 0,
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    expect(wrapper.findAll('[data-testid="assign-external"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="assign-internal"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="unassign-external"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="record-provision"]')).toHaveLength(1)
  })

  it('offers the rest of a position whose line was closed short to a new line', async () => {
    const lot = makeLot([
      makePosition({
        kind: 'external',
        order_item_id: 40,
        order_item_status: 'delivered',
        order_item_closed_short: true,
        quantity_remaining: 2,
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    expect(wrapper.findAll('[data-testid="assign-external"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="assign-internal"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('Closed short, 2 still open')
  })

  it('shows what is still open on a mixed position whose line was closed short', async () => {
    const lot = makeLot([
      makePosition({
        kind: 'mixed',
        order_item_id: 40,
        order_number: 'B-1',
        supplier_name: 'Supplier',
        order_item_status: 'delivered',
        order_item_closed_short: true,
        quantity_remaining: 2,
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    expect(wrapper.find('[data-testid="closed-short-rest"]').text()).toBe(
      'Closed short, 2 still open',
    )
    expect(wrapper.text()).toContain('B-1 (Supplier)')
  })

  it('lists the internal production orders of a mixed position', async () => {
    const lot = makeLot([
      makePosition({
        kind: 'mixed',
        order_item_id: 40,
        order_number: 'B-1',
        supplier_name: 'Supplier',
        order_item_status: 'delivered',
        quantity_remaining: 0,
        production_orders: [
          {
            id: 7,
            production_order_number: 'PO-7',
            status: 'queued',
            priority: 0,
            quantity: 3,
            quantity_completed: 1,
            machine_id: 5,
            machine_internal_name: 'CNC-05',
            machine_pool_id: null,
            machine_pool_name: null,
            conflicts: [],
            edit_version: 1,
          } as never,
        ],
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    const orders = wrapper.find('[data-testid="production-orders"]')
    expect(orders.exists()).toBe(true)
    expect(orders.text()).toContain('CNC-05')
    expect(orders.text()).toContain('1 / 3')
  })

  it('tags the newest line closed short once the rest is assigned internally', async () => {
    const lot = makeLot([
      makePosition({
        kind: 'mixed',
        order_item_id: 40,
        order_number: 'B-1',
        supplier_name: 'Supplier',
        order_item_status: 'delivered',
        order_item_closed_short: true,
        quantity_remaining: 0,
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    expect(wrapper.find('[data-testid="closed-short-rest"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="closed-short-tag"]').text()).toBe('Closed short')
  })

  it('leaves the tag to the rest hint while a rest is still open', async () => {
    const lot = makeLot([
      makePosition({
        kind: 'external',
        order_item_id: 40,
        order_number: 'B-1',
        supplier_name: 'Supplier',
        order_item_status: 'delivered',
        order_item_closed_short: true,
        quantity_remaining: 2,
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    expect(wrapper.find('[data-testid="closed-short-rest"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="closed-short-tag"]').exists()).toBe(false)
  })

  it('lists the earlier lines closed short below the newest line', async () => {
    const lot = makeLot([
      makePosition({
        kind: 'external',
        order_item_id: 42,
        order_number: 'B-3',
        supplier_name: 'Third',
        order_item_status: 'ordered',
        quantity_remaining: 0,
        earlier_order_lines: [
          {
            order_item_id: 41,
            order_id: 2,
            order_number: 'B-2',
            supplier_name: 'Second',
            quantity: 3,
            quantity_delivered: 3,
            unit: 'pcs',
            closed_short: true,
          },
          {
            order_item_id: 40,
            order_id: 1,
            order_number: 'B-1',
            supplier_name: 'First',
            quantity: 2,
            quantity_delivered: 2,
            unit: 'pcs',
            closed_short: true,
          },
        ],
      }),
    ])
    const wrapper = mountDock(lot, EVERYTHING)
    await flushPromises()

    const text = wrapper.text()
    expect(text.indexOf('B-3')).toBeLessThan(text.indexOf('B-2'))
    const lines = wrapper.findAll('[data-testid="earlier-order-line"]')
    expect(lines.map((line) => line.text())).toEqual([
      expect.stringMatching(/B-2 \(Second\), 3 pcs\s*Closed short/),
      expect.stringMatching(/B-1 \(First\), 2 pcs\s*Closed short/),
    ])
    expect(wrapper.find('[data-testid="closed-short-rest"]').exists()).toBe(false)
  })

  it('disables internal assignment, unassignment and provisions without their permissions', async () => {
    const lot = makeLot([
      makePosition({ id: 1 }),
      makePosition({
        id: 2,
        sequence: 2,
        kind: 'external',
        order_item_id: 40,
        order_item_status: 'requested',
        quantity_remaining: 0,
      }),
    ])
    const wrapper = mountDock(lot, [Permission.WRITE_ORDERS])
    await flushPromises()

    expect(button(wrapper, 'assign-external').attributes('disabled')).toBeUndefined()
    expect(button(wrapper, 'assign-internal').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'unassign-external').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'record-provision').attributes('disabled')).toBeDefined()
    expect(button(wrapper, 'append-position').attributes('disabled')).toBeDefined()
  })

  it('names the missing permission on each disabled position action', async () => {
    const lot = makeLot([
      makePosition({ id: 1 }),
      makePosition({
        id: 2,
        sequence: 2,
        kind: 'external',
        order_item_id: 40,
        order_item_status: 'requested',
        quantity_remaining: 0,
      }),
    ])
    const wrapper = mountDock(lot, [])
    await flushPromises()

    const tooltipOf = (testId: string) =>
      (button(wrapper, testId).element.parentElement as HTMLElement & { $_ptooltipValue?: string })
        .$_ptooltipValue
    expect(tooltipOf('assign-external')).toBe('This needs the permission Write Orders.')
    expect(tooltipOf('assign-internal')).toBe(
      'This needs the permission Write Production Orders.',
    )
    expect(tooltipOf('unassign-external')).toBe('This needs the permission Write Production Lots.')
    expect(tooltipOf('record-provision')).toBe('This needs the permission Write Production Lots.')
    expect(button(wrapper, 'manage-production').attributes('disabled')).toBeDefined()
    expect(tooltipOf('manage-production')).toBe(
      'This needs the permission Write Production Orders.',
    )
  })
})
