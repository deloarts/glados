import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'
import { makeLot } from '../../lots/__tests__/fixtures'

import type { LotResponse, ScrapPiecesResponse } from '../../types/productionLotsResponse'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { PrintTemplateResponse } from '@/features/print-labels'

// The "Print scrap tag" checkbox added to ScrapPiecesDialog.vue, and the
// follow-up print action it fires after a successful scrap booking, live in
// a sibling spec file rather than as cases added to ScrapPiecesDialog.spec.ts,
// following the convention of keeping new tests in their own new file.

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
  return makeProductionOrderResponse({
    id: 5,
    status: 'in_progress',
    quantity_completed: 4,
    ...overrides,
  })
}

function makeTemplate(overrides: Partial<PrintTemplateResponse> = {}): PrintTemplateResponse {
  return {
    id: 1,
    public_id: '44444444-4444-4444-4444-444444444444',
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    classifier: 'scrap_tag',
    output_kind: 'zpl',
    root_type: 'production_order_completion',
    trigger: 'pieces_scrapped',
    available_triggers: ['pieces_scrapped'],
    copies_rules: ['fixed'],
    source: '^XA^XZ',
    field_map: {},
    printer_id: null,
    printer_name: '',
    auto_print: false,
    copies_rule: 'fixed',
    copies_fixed: 1,
    max_copies: 50,
    design_dpi: null,
    label_width_mm: null,
    label_height_mm: null,
    paper: null,
    enabled: true,
    note: null,
    creator_id: null,
    creator_full_name: '',
    changes: [],
    ...overrides,
  }
}

function mockRoutes(lot: LotResponse, templates: PrintTemplateResponse[]): void {
  getMock.mockImplementation((url: string) => {
    if (url === `/production-lots/${lot.id}`) return Promise.resolve({ data: lot })
    if (url === '/print-templates/') return Promise.resolve({ data: templates })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function mockScrapAndPrintResponses(): void {
  postMock.mockImplementation((url: string) => {
    if (url === '/production-orders/5/scrap') {
      const response: ScrapPiecesResponse = {
        lot: makeLot([]) as unknown as ScrapPiecesResponse['lot'],
        created_lots: [],
      }
      return Promise.resolve({ data: response })
    }
    if (url === '/production-lots/1/print') {
      return Promise.resolve({
        data: {
          id: 1,
          public_id: '55555555-5555-5555-5555-555555555555',
          created: '2026-09-24T10:00:00Z',
          template_id: 1,
          printer_id: 9,
          classifier: 'scrap_tag',
          root_type: 'production_order_completion',
          root_id: 1,
          copies: 1,
          status: 'sent',
          error_message: null,
          document_bytes: 10,
          trigger: 'manual',
          actor_id: 1,
        },
      })
    }
    return Promise.reject(new Error(`unexpected POST ${url}`))
  })
}

interface ScrapDialogVm {
  open(target: ScrapDialogTarget): Promise<void>
  quantity: number | null
  reason: string | null
  printScrapTag: boolean
}

async function mountDialog() {
  return mountWithApp(ScrapPiecesDialog, { attachTo: document.body })
}

async function clickSubmit(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  const buttons = wrapper.findAllComponents({ name: 'Button' })
  await buttons.at(-1)!.trigger('click')
  await flushPromises()
}

describe('ScrapPiecesDialog - print scrap tag checkbox', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    mockScrapAndPrintResponses()
  })

  it('defaults on when the scrap_tag template has a printer configured', async () => {
    const order = makeOrder()
    mockRoutes({ ...makeLot([]), id: order.lot_id }, [makeTemplate({ printer_id: 9 })])

    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as ScrapDialogVm
    await vm.open({ kind: 'order', order })
    await flushPromises()

    expect(vm.printScrapTag).toBe(true)
    wrapper.unmount()
  })

  it('defaults off when the scrap_tag template has no printer configured', async () => {
    const order = makeOrder()
    mockRoutes({ ...makeLot([]), id: order.lot_id }, [makeTemplate({ printer_id: null })])

    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as ScrapDialogVm
    await vm.open({ kind: 'order', order })
    await flushPromises()

    expect(vm.printScrapTag).toBe(false)
    wrapper.unmount()
  })

  it('defaults off when the template list has no scrap_tag row at all', async () => {
    const order = makeOrder()
    mockRoutes({ ...makeLot([]), id: order.lot_id }, [])

    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as ScrapDialogVm
    await vm.open({ kind: 'order', order })
    await flushPromises()

    expect(vm.printScrapTag).toBe(false)
    wrapper.unmount()
  })

  it('prints the scrap tag for the returned lot after a successful submit when checked', async () => {
    const order = makeOrder()
    mockRoutes({ ...makeLot([]), id: order.lot_id }, [makeTemplate({ printer_id: 9 })])

    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as ScrapDialogVm
    await vm.open({ kind: 'order', order })
    await flushPromises()
    expect(vm.printScrapTag).toBe(true)

    vm.quantity = 2
    vm.reason = 'tool_breakage'
    await flushPromises()
    await clickSubmit(wrapper)

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/print', {
      printer_id: null,
      copies: null,
    })
    wrapper.unmount()
  })

  it('does not print the scrap tag when unchecked', async () => {
    const order = makeOrder()
    mockRoutes({ ...makeLot([]), id: order.lot_id }, [makeTemplate({ printer_id: null })])

    const wrapper = await mountDialog()
    const vm = wrapper.vm as unknown as ScrapDialogVm
    await vm.open({ kind: 'order', order })
    await flushPromises()
    expect(vm.printScrapTag).toBe(false)

    vm.quantity = 2
    vm.reason = 'tool_breakage'
    await flushPromises()
    await clickSubmit(wrapper)

    expect(postMock).not.toHaveBeenCalledWith('/production-lots/1/print', expect.anything())
    wrapper.unmount()
  })
})
