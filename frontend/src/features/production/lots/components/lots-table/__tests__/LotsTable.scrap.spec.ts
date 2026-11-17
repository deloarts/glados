import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeLotSummaryResponse, makeTestRouter } from '@/test-utils/factories'
import { useProductionLotsStore } from '../../../../stores/productionLotsStore'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { __resetLotNumberCache } from '../../../composables/useLotNumberCache'

// Same technique LotsTable.spec.ts/LotsTable.sourceApproval.spec.ts use for
// the nested OrderDetailDialog's useConfirm() call.
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: vi.fn<(options: unknown) => void>() }),
}))

// The status cell's replacement-lot links resolve ids to lot numbers through
// getLotsByIds -> GET /production-lots?ids=... (useLotNumberCache), mocked
// to hand back one fixed lot regardless of the requested ids, since every
// case here only ever asks for #5.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [{ id: 5, lot_number: 'LOT-5-REPL' }], total: 1, limit: 5, skip: 0 },
    }),
  },
}))

import LotsTable from '../LotsTable.vue'
import type { LotSummaryResponse } from '../../../../types/productionLotsResponse'

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    quantity: 8,
    quantity_completed: 8,
    status: 'in_progress',
    ...overrides,
  })
}

async function mountTable(lots: LotSummaryResponse[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const lotsStore = useProductionLotsStore()
  lotsStore.items = lots
  lotsStore.total = lots.length

  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(LotsTable, {
    pinia,
    props: {
      first: 0,
      rows: 25,
      showManageOrders: false,
      showManageProduction: false,
      showManageSource: false,
      openDetailById: vi.fn<(id: number) => Promise<void>>().mockResolvedValue(undefined),
    },
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
    },
  })
  await flushPromises()
  return wrapper
}

describe('LotsTable - scrap visibility', () => {
  beforeEach(() => {
    __resetLotNumberCache()
  })

  it('shows no scrap note for a lot that was never scrapped', async () => {
    const wrapper = await mountTable([makeLot({ quantity_scrapped: 0 })])

    expect(wrapper.text()).not.toContain('scrapped')
  })

  it('shows no scrap note when quantity_scrapped is left off the fixture (optional field)', async () => {
    const lot = makeLot()
    delete lot.quantity_scrapped
    const wrapper = await mountTable([lot])

    expect(wrapper.text()).not.toContain('scrapped')
  })

  it('shows a red note with the scrapped quantity and a replacement lot link', async () => {
    const wrapper = await mountTable([
      makeLot({ status: 'scrapped', quantity: 3, quantity_completed: 0, quantity_scrapped: 3, replacement_lot_ids: [5] }),
    ])
    await flushPromises()

    expect(wrapper.text()).toContain('3 scrapped')
    const link = wrapper.find('.scrap-note-link')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('LOT-5-REPL')
  })

  it('opens the replacement lot detail dialog when its link is clicked', async () => {
    const wrapper = await mountTable([
      makeLot({ quantity_scrapped: 1, replacement_lot_ids: [5] }),
    ])
    await flushPromises()

    await wrapper.find('.scrap-note-link').trigger('click')

    const { lotId, visible } = useLotDetail()
    expect(lotId.value).toBe(5)
    expect(visible.value).toBe(true)
  })

  it('renders the scrapped status tag with its own label', async () => {
    const wrapper = await mountTable([makeLot({ status: 'scrapped', quantity_scrapped: 3 })])

    expect(wrapper.text()).toContain(i18n.global.t('production.lots.status.scrapped'))
  })
})
