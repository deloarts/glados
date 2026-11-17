import { describe, it, expect, vi, beforeEach } from 'vitest'
import { computed, defineComponent, h } from 'vue'
import { createPinia, setActivePinia, storeToRefs } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse } from '@/test-utils/factories'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'

import type { LotResponse } from '../../../types/productionLotsResponse'

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

const getMock = vi.fn<(url: string) => Promise<unknown>>((url: string) => {
  if (/^\/production-lots\/\d+\/events$/.test(url)) return Promise.resolve({ data: [] })
  if (/^\/production-lots\/\d+\/changelog$/.test(url)) return Promise.resolve({ data: [] })
  if (/^\/production-lots\/\d+$/.test(url)) return Promise.resolve({ data: currentLotResponse })
  return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
})
const postMock = vi.fn<(url: string, payload?: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: {} }),
)

let currentLotResponse: unknown = null

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload?: unknown) => postMock(url, payload),
  },
}))

import { useLotDetailDialogs } from '../useLotDetailDialogs'

// Drives the composable inside a tiny host component (same technique
// useLotStructureDraft.spec.ts uses), since useLotDetailDialogs isn't
// itself a component. `result` is captured out of setup().
function mountDialogs(initialLot: LotResponse | null, lotId = 1) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const detailStore = useProductionLotDetailStore()
  if (initialLot) detailStore.lot = initialLot
  currentLotResponse = initialLot

  let result!: ReturnType<typeof useLotDetailDialogs>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        const { lot } = storeToRefs(useProductionLotDetailStore())
        result = useLotDetailDialogs(computed(() => lotId), lot)
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { wrapper, result, detailStore }
}

describe('useLotDetailDialogs', () => {
  beforeEach(() => {
    getMock.mockClear()
    postMock.mockClear()
    toastAddMock.mockClear()
    currentLotResponse = null
  })

  describe('hold / resume', () => {
    it('openHold clears any previous reason and shows the dialog', () => {
      const { result } = mountDialogs(makeLotResponse())
      result.holdReason.value = 'stale'

      result.openHold()

      expect(result.holdReason.value).toBe('')
      expect(result.showHold.value).toBe(true)
    })

    it('submitHold does nothing for a blank reason', async () => {
      const { result } = mountDialogs(makeLotResponse())
      result.showHold.value = true
      result.holdReason.value = '   '

      await result.submitHold()

      expect(postMock).not.toHaveBeenCalled()
      expect(result.showHold.value).toBe(true)
    })

    it('submitHold posts the trimmed reason and closes the dialog on success', async () => {
      const { result } = mountDialogs(makeLotResponse(), 5)
      result.showHold.value = true
      result.holdReason.value = '  waiting on tooling  '

      await result.submitHold()

      expect(postMock).toHaveBeenCalledWith('/production-lots/5/hold', {
        reason: 'waiting on tooling',
      })
      expect(result.showHold.value).toBe(false)
      expect(result.holding.value).toBe(false)
    })

    it('resumeLotAction posts to the resume endpoint for the current lot', async () => {
      const { result } = mountDialogs(makeLotResponse(), 7)

      await result.resumeLotAction()

      expect(postMock).toHaveBeenCalledWith('/production-lots/7/resume', undefined)
    })
  })

  describe('force status', () => {
    it('openForceStatus records which action and shows the dialog', () => {
      const { result } = mountDialogs(makeLotResponse())

      result.openForceStatus('cancel')

      expect(result.forceStatusAction.value).toBe('cancel')
      expect(result.showForceStatus.value).toBe(true)
    })

    it('confirmForceStatus completes the lot when the action is complete', async () => {
      const { result } = mountDialogs(makeLotResponse(), 3)
      result.openForceStatus('complete')

      await result.confirmForceStatus('done early')

      expect(postMock).toHaveBeenCalledWith('/production-lots/3/complete', {
        reason: 'done early',
        expected_edit_version: 0,
      })
      expect(result.showForceStatus.value).toBe(false)
      expect(result.forceStatusSubmitting.value).toBe(false)
    })

    it('confirmForceStatus cancels the lot when the action is cancel', async () => {
      const { result } = mountDialogs(makeLotResponse(), 3)
      result.openForceStatus('cancel')

      await result.confirmForceStatus(null)

      expect(postMock).toHaveBeenCalledWith('/production-lots/3/cancel', {
        reason: null,
        expected_edit_version: 0,
      })
      expect(result.showForceStatus.value).toBe(false)
    })
  })

  describe('audit trail', () => {
    it('loadEvents fetches events and the changelog, toggling eventsLoading around it', async () => {
      const { result } = mountDialogs(makeLotResponse(), 9)
      expect(result.eventsLoading.value).toBe(false)

      const promise = result.loadEvents()
      expect(result.eventsLoading.value).toBe(true)
      await promise

      expect(result.eventsLoading.value).toBe(false)
      expect(getMock).toHaveBeenCalledWith('/production-lots/9/events')
      expect(getMock).toHaveBeenCalledWith('/production-lots/9/changelog')
      expect(result.lotChangelog.value).toEqual([])
    })
  })

  describe('made / source item detail', () => {
    it('openMadeItemDetail opens the made-item popup for the lot\'s own made item', async () => {
      const { result } = mountDialogs(makeLotResponse({ made_item_id: 11 }))

      await result.openMadeItemDetail()

      expect(getMock).toHaveBeenCalledWith('/made-items/')
      expect(result.madeItemDetail.showDetail.value).toBe(true)
    })

    it('openSourceItemDetail opens the bought-item popup when sourced from a bought item', async () => {
      const { result } = mountDialogs(makeLotResponse({ source_bought_item_id: 22 }))

      await result.openSourceItemDetail()

      expect(getMock).toHaveBeenCalledWith('/bought-items/')
      expect(result.sourceBoughtItemDetail.showDetail.value).toBe(true)
    })

    it('openSourceItemDetail opens the made-item popup when sourced from a made item', async () => {
      const { result } = mountDialogs(makeLotResponse({ source_made_item_id: 33 }))

      await result.openSourceItemDetail()

      expect(getMock).toHaveBeenCalledWith('/made-items/')
      expect(result.sourceMadeItemDetail.showDetail.value).toBe(true)
    })

    it('openSourceItemDetail fetches and shows a raw source item when sourced from stock', async () => {
      const { result } = mountDialogs(makeLotResponse({ source_item_id: 44 }))

      await result.openSourceItemDetail()

      expect(result.showSourceItem.value).toBe(true)
    })
  })

  describe('demand detail', () => {
    it('openDemandDetail shows the demand detail dialog', () => {
      const { result } = mountDialogs(makeLotResponse())

      result.openDemandDetail()

      expect(result.showDemandDetail.value).toBe(true)
    })
  })

  describe('material source', () => {
    it('currentMaterialSource mirrors the lot\'s own source ids', () => {
      const { result } = mountDialogs(makeLotResponse({ source_bought_item_id: 5 }))

      expect(result.currentMaterialSource.value).toEqual({
        bought_item_id: 5,
        source_item_id: null,
        made_item_id: null,
      })
    })
  })

  describe('source approval', () => {
    it('approveSource posts to the approve endpoint and shows a success toast', async () => {
      const lot = makeLotResponse({
        lot_number: 'LOT-0042',
        source_approval_status: 'pending',
        edit_version: 4,
      })
      const { result } = mountDialogs(lot, 1)
      currentLotResponse = lot

      await result.approveSource()
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/production-lots/1/source/approve', {
        expected_edit_version: 4,
      })
      expect(toastAddMock).toHaveBeenCalledWith(
        expect.objectContaining({ severity: 'success', summary: 'LOT-0042' }),
      )
    })

    it.each([
      ['approveSource', (r: ReturnType<typeof useLotDetailDialogs>) => r.approveSource()],
      ['confirmRejectSource', (r: ReturnType<typeof useLotDetailDialogs>) => r.confirmRejectSource('Wrong bar')],
    ])('%s reloads a stale lot after a 409 and shows the server reason', async (_, act) => {
      const stale = makeLotResponse({ source_approval_status: 'pending', edit_version: 4 })
      const { result, detailStore } = mountDialogs(stale, 1)
      currentLotResponse = makeLotResponse({
        source_approval_status: 'approved',
        source_item_id: 9,
        edit_version: 5,
      })
      postMock.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 409, data: { detail: 'The lot was changed by someone else.' } },
      })

      await act(result)
      await flushPromises()

      expect(getMock).toHaveBeenCalledWith('/production-lots/1')
      expect(detailStore.lot?.edit_version).toBe(5)
      expect(detailStore.lot?.source_approval_status).toBe('approved')
      expect(toastAddMock).toHaveBeenCalledWith(
        expect.objectContaining({
          severity: 'error',
          detail: 'The lot was changed by someone else.',
        }),
      )
    })

    it('leaves the lot as it is after another error', async () => {
      const { result } = mountDialogs(makeLotResponse({ source_approval_status: 'pending' }), 1)
      postMock.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 422, data: { detail: 'Invalid.' } },
      })

      await result.approveSource()
      await flushPromises()

      expect(getMock).not.toHaveBeenCalledWith('/production-lots/1')
    })
  })
})
