import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'

const getLots = vi.fn<(params: unknown) => Promise<{ items: unknown[] }>>()
const getProducts = vi.fn<(params: unknown) => Promise<{ items: unknown[] }>>()
const fetchProjectsByIds = vi.fn<(ids: number[]) => Promise<LookupOption[]>>()

vi.mock('@/features/production', () => ({ getLots: (p: unknown) => getLots(p) }))
vi.mock('@/features/products', () => ({ getProducts: (p: unknown) => getProducts(p) }))
vi.mock('@/shared/components/demands/demandProjectLookup', () => ({
  fetchDemandProjectOptions: vi.fn<() => Promise<LookupOption[]>>().mockResolvedValue([]),
  fetchDemandProjectsByIds: (ids: number[]) => fetchProjectsByIds(ids),
}))

import ExternalWorkLotFilter from '../ExternalWorkLotFilter.vue'

describe('ExternalWorkLotFilter', () => {
  beforeEach(() => {
    getLots.mockResolvedValue({
      items: [{ id: 4, lot_number: 'LOT-26-00004', made_item_article_name: 'Konsole' }],
    })
    getProducts.mockResolvedValue({ items: [{ id: 7, product_number: 'PRD-0815' }] })
    fetchProjectsByIds.mockResolvedValue([{ id: 1, label: 'P26448' }])
  })

  it('sums up the lots, projects and products picked in one field', async () => {
    const wrapper = mountWithApp(ExternalWorkLotFilter, {
      props: { column: 'Lot / Project', lotIds: [4], projectIds: [1], productIds: [7] },
      global: { stubs: { LookupMultiSelect: true } },
    })
    await flushPromises()

    const field = wrapper.get('[data-testid="external-work-lot-filter-field"]')
    expect((field.element as HTMLInputElement).value).toBe('LOT-26-00004, P26448, PRD-0815')
    wrapper.unmount()
  })

  it('clears all three at once', async () => {
    const wrapper = mountWithApp(ExternalWorkLotFilter, {
      props: { column: 'Lot / Project', lotIds: [4], projectIds: [1], productIds: [] },
      global: { stubs: { LookupMultiSelect: true } },
    })
    await flushPromises()

    await wrapper.get('[data-testid="external-work-lot-filter-clear"]').trigger('click')

    expect(wrapper.emitted('update:lotIds')?.at(-1)).toEqual([[]])
    expect(wrapper.emitted('update:projectIds')?.at(-1)).toEqual([[]])
    wrapper.unmount()
  })
})
