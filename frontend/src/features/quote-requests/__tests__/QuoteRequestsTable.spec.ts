import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { PageResponse } from '@/core/api/types'
import type { QuoteRequestFilterParams } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'
import { makeLine, makeRequest, makeRow, makeQuote } from './quoteRequestFixtures'

const getQuoteRequestsMock =
  vi.fn<(params?: QuoteRequestFilterParams) => Promise<PageResponse<QuoteRequestResponse>>>()
vi.mock('../api/getQuoteRequests', () => ({
  getQuoteRequests: (params?: QuoteRequestFilterParams) => getQuoteRequestsMock(params),
}))

import QuoteRequestsTable from '../components/QuoteRequestsTable.vue'

describe('QuoteRequestsTable', () => {
  beforeEach(() => {
    getQuoteRequestsMock.mockReset().mockResolvedValue({
      items: [
        makeRequest({
          lines: [makeLine({ item_name: 'Screw M6' }), makeLine({ id: 2, position: 2, item_name: 'Washer' })],
          suppliers: [
            makeRow({ quotes: [makeQuote({ line_id: 1, unit_price: 120 })] }),
          ],
        }),
      ],
      total: 1,
      limit: 25,
      skip: 0,
    })
  })

  it('asks for the open requests unless closed ones are shown', async () => {
    const wrapper = mountWithApp(QuoteRequestsTable, { props: { showClosed: false } })
    await flushPromises()

    expect(getQuoteRequestsMock.mock.calls[0]?.[0]?.status).toEqual(['draft', 'sent'])

    await wrapper.setProps({ showClosed: true })
    await flushPromises()
    expect(getQuoteRequestsMock.mock.calls.at(-1)?.[0]?.status).toBeUndefined()
  })

  it('expands a row into the lines of the request', async () => {
    const wrapper = mountWithApp(QuoteRequestsTable, { props: { showClosed: false } })
    await flushPromises()
    expect(wrapper.find('[data-testid="quote-request-lines"]').exists()).toBe(false)

    await wrapper.find('[data-testid="quote-requests-table"] tbody tr').trigger('click')
    await flushPromises()

    const lines = wrapper.find('[data-testid="quote-request-lines"]')
    expect(lines.exists()).toBe(true)
    expect(lines.text()).toContain('Screw M6')
    expect(lines.text()).toContain('Washer')
  })
})
