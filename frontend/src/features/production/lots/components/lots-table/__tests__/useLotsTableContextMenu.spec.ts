import { describe, it, expect, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import { useLotsTableContextMenu } from '../useLotsTableContextMenu'
import type { LotsTableContextMenuActions } from '../useLotsTableContextMenu'
import type { LotSummaryPositionResponse, LotSummaryResponse } from '../../../../types/productionLotsResponse'
import { lotActions } from '../../../__tests__/fixtures'

// Drives the composable inside a tiny host component, same technique
// useLotPositionActions.spec.ts uses: useLotsTableContextMenu calls
// useI18n()/useClipboard() internally, which need an active component
// instance.
function mountContextMenu(
  canWriteProductionOrders = true,
  actionsOverride: Partial<LotsTableContextMenuActions> = {},
) {
  const actions: LotsTableContextMenuActions = {
    openLot: vi.fn<(lot: LotSummaryResponse) => void>(),
    editSteps: vi.fn<(lot: LotSummaryResponse) => void>(),
    setRequiredDelivery: vi.fn<(lot: LotSummaryResponse) => void>(),
    forceStatus: vi.fn<(lot: LotSummaryResponse, action: 'complete' | 'cancel') => void>(),
    addSourceItem: vi.fn<(lot: LotSummaryResponse) => void>(),
    demandSourceItem: vi.fn<(lot: LotSummaryResponse) => void>(),
    scrapPieces: vi.fn<(lot: LotSummaryResponse) => void>(),
    inspectionReport: vi.fn<(lot: LotSummaryResponse) => void>(),
    ...actionsOverride,
  }

  let result!: ReturnType<typeof useLotsTableContextMenu>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useLotsTableContextMenu(
          (data) => data as LotSummaryResponse,
          ref(true),
          ref(true),
          ref(true),
          ref(canWriteProductionOrders),
          () => false,
          () => Promise.resolve(),
          vi.fn<(lot: LotSummaryResponse) => void>(),
          actions,
        )
        return () => h('div')
      },
    }),
  )
  return { wrapper, result, actions }
}

function makePosition(overrides: Partial<LotSummaryPositionResponse> = {}): LotSummaryPositionResponse {
  return {
    id: 1,
    kind: 'internal',
    delivery_date: null,
    delivery_record_count: 0,
    expected_delivery_date: null,
    expected_pickup_date: null,
    order_id: null,
    order_item_id: null,
    order_item_items_per_unit: 1,
    order_item_quantity: null,
    order_item_quantity_delivered: null,
    order_item_status: '',
    order_item_unit: '',
    order_number: '',
    ordered_by_name: null,
    production_orders: [],
    ready_for_pickup_date: null,
    ...overrides,
  } as LotSummaryPositionResponse
}

// The actions default to what the backend offers a manager of lots on a lot
// in that status.
function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    actions: lotActions(overrides.status ?? 'in_progress'),
    status: 'in_progress',
    positions: [makePosition()],
    ...overrides,
  })
}

function scrapItem(items: ReturnType<typeof useLotsTableContextMenu>['contextMenuItems']['value']) {
  return items.find((i) => i.icon === 'mdi mdi-delete-alert-outline')
}

describe('useLotsTableContextMenu - scrap pieces entry', () => {
  it('is enabled for a non-terminal lot with an internal position, and calls scrapPieces on command', () => {
    const { result, actions } = mountContextMenu()
    const lot = makeLot()
    result.contextMenuItem.value = lot

    const item = scrapItem(result.contextMenuItems.value)
    expect(item).toBeTruthy()
    expect(item?.disabled).toBe(false)

    item?.command?.({ originalEvent: new Event('click'), item: item! })
    expect(actions.scrapPieces).toHaveBeenCalledWith(lot)
  })

  it('is enabled for a mixed position too', () => {
    const { result } = mountContextMenu()
    result.contextMenuItem.value = makeLot({ positions: [makePosition({ kind: 'mixed' })] })

    expect(scrapItem(result.contextMenuItems.value)?.disabled).toBe(false)
  })

  it('is disabled without the production-order write permission', () => {
    const { result } = mountContextMenu(false)
    result.contextMenuItem.value = makeLot()

    expect(scrapItem(result.contextMenuItems.value)?.disabled).toBe(true)
  })

  it.each(['completed', 'canceled', 'scrapped'] as const)(
    'is disabled for a terminal lot (%s)',
    (status) => {
      const { result } = mountContextMenu()
      result.contextMenuItem.value = makeLot({ status })

      expect(scrapItem(result.contextMenuItems.value)?.disabled).toBe(true)
    },
  )

  it('is disabled for a lot with no internal or mixed position', () => {
    const { result } = mountContextMenu()
    result.contextMenuItem.value = makeLot({ positions: [makePosition({ kind: 'external' })] })

    expect(scrapItem(result.contextMenuItems.value)?.disabled).toBe(true)
  })
})

describe('useLotsTableContextMenu - add source item entry', () => {
  function addSourceItem(items: ReturnType<typeof useLotsTableContextMenu>['contextMenuItems']['value']) {
    return items.find((i) => i.icon === 'mdi mdi-database-import-outline')
  }

  it('is enabled on a lot that is not finished', () => {
    const { result } = mountContextMenu()
    result.contextMenuItem.value = makeLot({ input_demand_id: null })

    expect(addSourceItem(result.contextMenuItems.value)?.disabled).toBe(false)
  })

  it.each(['completed', 'canceled', 'scrapped'] as const)(
    'is disabled on a finished lot (%s), which the server offers no switch on',
    (status) => {
      const { result } = mountContextMenu()
      result.contextMenuItem.value = makeLot({ status, input_demand_id: null })

      expect(addSourceItem(result.contextMenuItems.value)?.disabled).toBe(true)
    },
  )

  it('carries the reason the Change button shows as title once it is disabled', () => {
    const { result } = mountContextMenu()

    result.contextMenuItem.value = makeLot({ status: 'canceled', input_demand_id: null })
    expect(addSourceItem(result.contextMenuItems.value)?.title).toBe(
      i18n.global.t('production.lots.detail.materialSource.finishedTooltip'),
    )

    // An ordered demand can still be switched; a fulfilled one leaves nothing to switch.
    result.contextMenuItem.value = makeLot({ input_demand_id: 7, demand_status: 'fulfilled' })
    expect(addSourceItem(result.contextMenuItems.value)).toMatchObject({
      disabled: true,
      title: i18n.global.t('production.lots.detail.materialSource.lockedTooltip'),
    })

    result.contextMenuItem.value = makeLot({ input_demand_id: null })
    expect(addSourceItem(result.contextMenuItems.value)?.title).toBeUndefined()
  })
})
