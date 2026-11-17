import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeSourceItemDemandResponse } from '@/test-utils/factories'


const getMock = vi.fn<(url: string) => Promise<unknown>>()
const postMock = vi.fn<(url: string, body?: unknown) => Promise<unknown>>()

const substitutedSummary: SourceItemDemandSummaryResponse = {
  demand_item_id: 1,
  unit: 'PCS',
  total: 5,
  allocated: 5,
  fulfilled_from_stock: 0,
  ordered: 5,
  delivered: 0,
  remaining: 5,
  unallocated: 0,
  pending: 5,
  in_transit: 0,
  is_fully_allocated: true,
  is_fully_delivered: false,
  unit_mismatch: false,
  substitutions: [
    {
      substitute_source_item_id: 2,
      substitute_item_article_name: '12mm',
      substitute_item_order_code_1: 'RB-12',
      substitute_item_specification: '',
      substitute_reason: 'Preferred stock size',
      quantity: 5,
    },
  ],
  order_ids: [],
  order_numbers: [],
}

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, body?: unknown) => postMock(url, body),
  },
}))

import SourceItemDemandDetailDialog from '../SourceItemDemandDetailDialog.vue'
import type { SourceItemDemandResponse, SourceItemDemandSummaryResponse } from '@/features/source-items'

function mountDialog(demand: SourceItemDemandResponse) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(SourceItemDemandDetailDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, demand },
    global: {
      plugins: [ConfirmationService],
    },
  })
  return wrapper
}

describe('SourceItemDemandDetailDialog', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 0, skip: 0 } })
    postMock.mockImplementation((url: string) => {
      if (url === '/source-item-allocations/demands/summary-batch') {
        return Promise.resolve({ data: { 1: substitutedSummary } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('shows an "Ordered as substitute" section when the allocation summary carries a substitution', async () => {
    const wrapper = mountDialog(makeSourceItemDemandResponse())
    await wrapper.setProps({ visible: true })
    await flushPromises()

    // Dialog teleports to document.body, so query there, not the wrapper
    // root (see OrderCreateForm.spec.ts for the same caveat).
    const section = document.body.querySelector('.subst-section')
    expect(section).not.toBeNull()
    expect(section!.querySelector('.subst-row-code')!.textContent).toBe('RB-12')
    expect(section!.querySelector('.subst-row-name')!.textContent).toBe('12mm')
    expect(section!.querySelector('.subst-row-reason')!.textContent).toContain(
      'Preferred stock size',
    )

    wrapper.unmount()
  })

  it('omits the substitution section when the summary has none', async () => {
    postMock.mockImplementation((url: string) => {
      if (url === '/source-item-allocations/demands/summary-batch') {
        return Promise.resolve({ data: { 1: { ...substitutedSummary, substitutions: [] } } })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mountDialog(makeSourceItemDemandResponse())
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(document.body.querySelector('.subst-section')).toBeNull()

    wrapper.unmount()
  })
})
