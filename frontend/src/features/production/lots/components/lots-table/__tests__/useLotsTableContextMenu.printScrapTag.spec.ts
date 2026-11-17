import { describe, it, expect, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import { useLotsTableContextMenu } from '../useLotsTableContextMenu'
import type { LotsTableContextMenuActions } from '../useLotsTableContextMenu'
import type { LotPrintClassifier } from '../useLotPrinting'
import type { LotSummaryPositionResponse, LotSummaryResponse } from '../../../../types/productionLotsResponse'

// The lot context menu's print submenu "Scrap tag" entry, beside the lot
// label/docket entries, in a sibling spec file rather than in
// useLotsTableContextMenu.spec.ts, same convention as that file's own
// "not touched" pin.

function mountContextMenu(options: {
  canPrint?: boolean
  isPrintingScrapTag?: boolean
  onPrintLot?: (lot: LotSummaryResponse, classifier: LotPrintClassifier) => Promise<void>
} = {}) {
  const {
    canPrint = true,
    isPrintingScrapTag = false,
    onPrintLot = vi.fn<(lot: LotSummaryResponse, classifier: LotPrintClassifier) => Promise<void>>().mockResolvedValue(
      undefined,
    ),
  } = options

  const actions: LotsTableContextMenuActions = {
    openLot: vi.fn<(lot: LotSummaryResponse) => void>(),
    editSteps: vi.fn<(lot: LotSummaryResponse) => void>(),
    setRequiredDelivery: vi.fn<(lot: LotSummaryResponse) => void>(),
    forceStatus: vi.fn<(lot: LotSummaryResponse, action: 'complete' | 'cancel') => void>(),
    addSourceItem: vi.fn<(lot: LotSummaryResponse) => void>(),
    demandSourceItem: vi.fn<(lot: LotSummaryResponse) => void>(),
    scrapPieces: vi.fn<(lot: LotSummaryResponse) => void>(),
    inspectionReport: vi.fn<(lot: LotSummaryResponse) => void>(),
  }

  let result!: ReturnType<typeof useLotsTableContextMenu>
  mountWithApp(
    defineComponent({
      setup() {
        result = useLotsTableContextMenu(
          (data) => data as LotSummaryResponse,
          ref(true),
          ref(true),
          ref(canPrint),
          ref(true),
          (_lot, classifier) => classifier === 'scrap_tag' && isPrintingScrapTag,
          onPrintLot,
          vi.fn<(lot: LotSummaryResponse) => void>(),
          actions,
        )
        return () => h('div')
      },
    }),
  )
  return { result, onPrintLot }
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

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    quantity_scrapped: 0,
    status: 'in_progress',
    positions: [makePosition()],
    ...overrides,
  })
}

function scrapTagItem(items: ReturnType<typeof useLotsTableContextMenu>['contextMenuItems']['value']) {
  const printMenu = items.find((i) => i.icon === 'mdi mdi-printer-outline')
  return printMenu?.items?.find((i) => i.label === 'Scrap Tag')
}

describe('useLotsTableContextMenu - print submenu scrap tag entry', () => {
  it('is enabled when the lot has scrapped pieces and printing is allowed', () => {
    const { result } = mountContextMenu()
    result.contextMenuItem.value = makeLot({ quantity_scrapped: 2 })

    const item = scrapTagItem(result.contextMenuItems.value)
    expect(item).toBeTruthy()
    expect(item?.disabled).toBe(false)
  })

  it('is disabled when the lot has never been scrapped', () => {
    const { result } = mountContextMenu()
    result.contextMenuItem.value = makeLot({ quantity_scrapped: 0 })

    expect(scrapTagItem(result.contextMenuItems.value)?.disabled).toBe(true)
  })

  it('is disabled without the print permission even when scrapped', () => {
    const { result } = mountContextMenu({ canPrint: false })
    result.contextMenuItem.value = makeLot({ quantity_scrapped: 2 })

    expect(scrapTagItem(result.contextMenuItems.value)?.disabled).toBe(true)
  })

  it('is disabled mid-flight while a scrap tag print is already in progress for this lot', () => {
    const { result } = mountContextMenu({ isPrintingScrapTag: true })
    result.contextMenuItem.value = makeLot({ quantity_scrapped: 2 })

    expect(scrapTagItem(result.contextMenuItems.value)?.disabled).toBe(true)
  })

  it('calls onPrintLot with the scrap_tag classifier on command', () => {
    const { result, onPrintLot } = mountContextMenu()
    const lot = makeLot({ quantity_scrapped: 2 })
    result.contextMenuItem.value = lot

    const item = scrapTagItem(result.contextMenuItems.value)
    item?.command?.({ originalEvent: new Event('click'), item: item! })

    expect(onPrintLot).toHaveBeenCalledWith(lot, 'scrap_tag')
  })
})
