import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { QuoteRequestAwardRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestAwardResponse, QuoteRequestResponse } from '../types/quoteRequestsResponse'
import { makeLine, makeRequest, makeRow } from './quoteRequestFixtures'

const awardMock =
  vi.fn<(id: number, payload: QuoteRequestAwardRequest) => Promise<QuoteRequestAwardResponse>>()
vi.mock('../api/awardQuoteRequest', () => ({
  awardQuoteRequest: (id: number, payload: QuoteRequestAwardRequest) => awardMock(id, payload),
}))
vi.mock('../api/getSupplierDraftOrders', () => ({
  getSupplierDraftOrders: () => Promise.resolve([]),
}))

import QuoteAwardDialog from '../components/QuoteAwardDialog.vue'

interface AwardDialogVm {
  open(request: QuoteRequestResponse, chosen: Map<number, number>): Promise<void>
}

describe('QuoteAwardDialog', () => {
  beforeEach(() => {
    awardMock.mockReset().mockResolvedValue({
      request: makeRequest({ status: 'awarded' }),
      orders: [
        {
          order_id: 40,
          order_number: 'ORD-26-00040',
          supplier_id: 21,
          supplier_name: 'Acme',
          created: true,
          line_ids: [1],
        },
      ],
      warnings: [{ line_id: 1, kind: 'share_capped', message: 'Line 1: demand #3 took 2.' }],
    })
  })

  it('books the offer costs of the lines a supplier won and shows what the award did', async () => {
    const request = makeRequest({
      lines: [makeLine({ id: 1 }), makeLine({ id: 2, position: 2 })],
      suppliers: [
        makeRow({
          id: 11,
          extra_costs: [
            { kind: 'shipping', amount: 1500, position: 1, label: null, note: null, line_id: null },
            { kind: 'setup', amount: 900, position: 2, label: null, note: null, line_id: 2 },
          ],
        }),
      ],
    })
    const wrapper = mountWithApp(QuoteAwardDialog, { attachTo: document.body })
    await (wrapper.vm as unknown as AwardDialogVm).open(request, new Map([[1, 11]]))
    await flushPromises()

    ;(document.body.querySelector('[data-testid="award-submit"]') as HTMLButtonElement).click()
    await flushPromises()

    expect(awardMock).toHaveBeenCalledWith(7, {
      expected_edit_version: 2,
      awards: [{ line_id: 1, supplier_row_id: 11 }],
      suppliers: [
        {
          supplier_row_id: 11,
          target_order_id: null,
          extra_costs: [{ kind: 'shipping', amount: 1500, label: null, note: null, line_id: null }],
        },
      ],
    })
    expect(document.body.textContent).toContain('ORD-26-00040')
    expect(document.body.textContent).toContain('Line 1: demand #3 took 2.')
    wrapper.unmount()
  })
})
