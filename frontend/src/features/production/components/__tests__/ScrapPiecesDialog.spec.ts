import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'
import { makeLot, makePosition } from '../../lots/__tests__/fixtures'

import type {
  LotPositionProductionOrderSummary,
  LotResponse,
  ScrapPiecesResponse,
} from '../../types/productionLotsResponse'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

const getMock = vi.fn<(url: string) => Promise<unknown>>()
const postMock = vi.fn<(url: string, payload?: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload?: unknown) => postMock(url, payload),
  },
}))

import ScrapPiecesDialog from '../ScrapPiecesDialog.vue'
import type { ScrapDialogTarget } from '../ScrapPiecesDialog.vue'

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({ status: 'in_progress', quantity_completed: 4, ...overrides })
}

function makeOrderSummary(
  overrides: Partial<LotPositionProductionOrderSummary> = {},
): LotPositionProductionOrderSummary {
  return {
    id: 101,
    production_order_number: 'PO-101',
    edit_version: 0,
    status: 'in_progress',
    priority: 'normal',
    quantity: 10,
    quantity_completed: 4,
    machine_id: 1,
    machine_internal_name: 'Machine 1',
    machine_pool_id: null,
    machine_pool_name: '',
    conflicts: [],
    ...overrides,
  }
}

// Every GET this dialog can issue is for a single lot (getLot(id)): routed
// by url, defaulting to the given fixture regardless of which lot id was
// asked for since every test here only ever has one lot in play.
function mockGetLot(lot: LotResponse): void {
  getMock.mockImplementation((url: string) => {
    if (url === `/production-lots/${lot.id}`) return Promise.resolve({ data: lot })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function mockScrapResponse(): void {
  // Only `created_lots` (checked by the toast branch) matters to these
  // tests. `lot` just needs to satisfy the response shape.
  const response: ScrapPiecesResponse = {
    lot: makeLot([]) as unknown as ScrapPiecesResponse['lot'],
    created_lots: [],
  }
  postMock.mockResolvedValue({ data: response })
}

interface ScrapDialogVm {
  open(target: ScrapDialogTarget): Promise<void>
  quantity: number | null
  reason: string | null
  note: string
  createReplacement: boolean
  selectedPositionId: number | null
  selectedOrderId: number | null
  selectPosition(id: number | null): void
  canSubmit: boolean
  maxQuantity: number | null
  showOrderSelect: boolean
  openOrdersForPosition: LotPositionProductionOrderSummary[]
}

async function mountDialog() {
  const wrapper = mountWithApp(ScrapPiecesDialog, { attachTo: document.body })
  return wrapper
}

async function clickSubmit(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  await buttons.at(-1)!.trigger('click')
  await flushPromises()
}

describe('ScrapPiecesDialog', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    mockScrapResponse()
  })

  describe('order mode', () => {
    it('defaults quantity to 1 with no reason picked, capped at the order remainder', async () => {
      const order = makeOrder({ quantity: 10, quantity_completed: 4 })
      mockGetLot({ ...makeLot([]), id: order.lot_id, required_delivery_date: null })

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'order', order })
      await flushPromises()

      expect(vm.quantity).toBe(1)
      expect(vm.maxQuantity).toBe(6)
      expect(vm.canSubmit).toBe(false) // no reason yet

      wrapper.unmount()
    })

    it('is invalid once the quantity exceeds the order remainder (cap validation)', async () => {
      const order = makeOrder({ quantity: 10, quantity_completed: 4 })
      mockGetLot({ ...makeLot([]), id: order.lot_id })

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'order', order })
      await flushPromises()

      vm.reason = 'tool_breakage'
      vm.quantity = 6
      await flushPromises()
      expect(vm.canSubmit).toBe(true)

      vm.quantity = 7
      await flushPromises()
      expect(vm.canSubmit).toBe(false)

      wrapper.unmount()
    })

    it('submits to the production-order scrap endpoint with the chosen fields', async () => {
      const order = makeOrder({ id: 5, quantity: 10, quantity_completed: 4 })
      mockGetLot({ ...makeLot([]), id: order.lot_id })

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'order', order })
      await flushPromises()

      vm.quantity = 2
      vm.reason = 'tool_breakage'
      vm.note = 'Broke during turning'
      await flushPromises()

      await clickSubmit(wrapper)

      expect(postMock).toHaveBeenCalledWith('/production-orders/5/scrap', {
        quantity: 2,
        reason: 'tool_breakage',
        note: 'Broke during turning',
        create_replacement: true,
        expected_edit_version: 0,
        expected_lot_edit_version: 0,
      })
      expect(wrapper.emitted('scrapped')).toHaveLength(1)

      wrapper.unmount()
    })
  })

  describe('lot mode', () => {
    function makeTwoPositionLot(overrides: {
      firstOrders?: LotPositionProductionOrderSummary[]
      secondOrders?: LotPositionProductionOrderSummary[]
    } = {}): LotResponse {
      const first = makePosition({
        id: 10,
        sequence: 1,
        kind: 'internal',
        status: 'in_progress',
        quantity: 10,
        quantity_completed: 4,
        production_orders: overrides.firstOrders ?? [makeOrderSummary({ id: 101 })],
      })
      const second = makePosition({
        id: 20,
        sequence: 2,
        kind: 'internal',
        status: 'pending',
        quantity: 10,
        quantity_completed: 0,
        production_orders: overrides.secondOrders ?? [],
      })
      return { ...makeLot([first, second]), id: 1, required_delivery_date: '2026-08-20' }
    }

    it('fetches the lot and preselects the in-progress position, auto-resolving its one open order', async () => {
      const lot = makeTwoPositionLot()
      mockGetLot(lot)

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'lot', lotId: 1 })
      await flushPromises()

      expect(vm.selectedPositionId).toBe(10)
      expect(vm.selectedOrderId).toBe(101)
      expect(vm.showOrderSelect).toBe(false)
      expect(vm.maxQuantity).toBe(6) // order quantity 10 - completed 4

      wrapper.unmount()
    })

    it('shows an order selector when the position has more than one open order, and blocks submit until one is picked', async () => {
      const lot = makeTwoPositionLot({
        firstOrders: [
          makeOrderSummary({ id: 101, status: 'in_progress' }),
          makeOrderSummary({ id: 102, status: 'queued', quantity: 5, quantity_completed: 0 }),
        ],
      })
      mockGetLot(lot)

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'lot', lotId: 1 })
      await flushPromises()

      expect(vm.showOrderSelect).toBe(true)
      expect(vm.selectedOrderId).toBeNull()
      expect(vm.openOrdersForPosition.map((o) => o.id)).toEqual([101, 102])

      vm.reason = 'tool_breakage'
      vm.quantity = 1
      await flushPromises()
      expect(vm.canSubmit).toBe(false)

      vm.selectedOrderId = 102
      await flushPromises()
      expect(vm.canSubmit).toBe(true)

      wrapper.unmount()
    })

    it('warns and blocks submit when the selected position has no open production order', async () => {
      const lot = makeTwoPositionLot()
      mockGetLot(lot)

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'lot', lotId: 1 })
      await flushPromises()

      vm.selectPosition(20) // no open orders on this position
      vm.reason = 'tool_breakage'
      vm.quantity = 1
      await flushPromises()

      expect(vm.canSubmit).toBe(false)
      expect(document.body.textContent).toContain('no open production order')

      wrapper.unmount()
    })

    it('opt-out: unchecking Create replacement lot sends create_replacement false to the lot-scoped endpoint', async () => {
      const lot = makeTwoPositionLot()
      mockGetLot(lot)

      const wrapper = await mountDialog()
      const vm = wrapper.vm as unknown as ScrapDialogVm
      await vm.open({ kind: 'lot', lotId: 1 })
      await flushPromises()

      vm.quantity = 2
      vm.reason = 'machine_fault'
      vm.createReplacement = false
      await flushPromises()
      expect(vm.canSubmit).toBe(true)

      await clickSubmit(wrapper)

      expect(postMock).toHaveBeenCalledWith('/production-lots/1/scrap', {
        quantity: 2,
        reason: 'machine_fault',
        note: undefined,
        create_replacement: false,
        position_id: 10,
        production_order_id: 101,
        expected_edit_version: 0,
      })
      expect(wrapper.emitted('scrapped')).toHaveLength(1)

      wrapper.unmount()
    })
  })
})
