import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


const demandPage = {
  items: [
    {
      id: 7,
      public_id: 'demand-uuid',
      status: 'open',
      created: '2026-03-01',
      changed: null,
      quantity: 5,
      unit: 'pcs',
      items_per_unit: 1,
      high_priority: false,
      notify_on_delivery: false,
      note: null,
      desired_delivery_date: '2026-04-01',
      creator_id: 1,
      creator: { id: 1, username: 'creator', full_name: 'Creator', email: 'c@e.com' },
      made_item_id: 1,
      item_part_number: 'PN-1',
      item_article_name: 'Article',
      project_id: 3,
      project_number: 'P-100',
      project_customer: 'Customer',
      project_description: '',
      project_status: 'active',
      is_alteration: false,
      alteration_of_made_item_id: null,
      alteration_of_made_item_part_number: '',
      alteration_of_made_item_article_name: '',
    },
  ],
  total: 1,
  limit: 100,
  skip: 0,
}

const lotPage = {
  items: [
    {
      id: 11,
      public_id: 'lot-uuid',
      lot_number: 'L-2026-011',
      quantity: 5,
      quantity_completed: 2,
      status: 'in_progress',
      priority: 'normal',
      created: '2026-03-05',
      required_delivery_date: null,
      made_item_id: 1,
      made_item_part_number: 'PN-1',
      made_item_article_name: 'Article',
      made_item_revision: 'A',
      made_item_material: '1.0037',
      source_bought_item_id: null,
      source_item_id: null,
      source_made_item_id: null,
      source_label: '',
      source_sublabel: '',
      demand_status: 'open',
      is_alteration: false,
      project_id: 3,
      project_number: 'P-100',
      project_customer: 'Customer',
      creator_id: 1,
      creator: null,
      input_demand_id: null,
      steps: [],
      positions: [],
    },
  ],
  total: 1,
  limit: 100,
  skip: 0,
}

type GetConfig = { params?: Record<string, unknown> } | undefined

const get = vi
  .fn<(url: string, config: GetConfig) => Promise<unknown>>()
  .mockImplementation((url: string) =>
    Promise.resolve({ data: url.includes('production-lots') ? lotPage : demandPage }),
  )

// The created cells load the user list for the creator's card; it stays
// empty here so the request does not reach the API mock below.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

vi.mock('@/core/api', () => ({
  default: { get: (url: string, config: GetConfig) => get(url, config) },
}))

import MadeItemHistoryDialog from '../MadeItemHistoryDialog.vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { MadeItemResponse } from '@/features/made-items'

const item = { id: 1, article_name: 'Article' } as MadeItemResponse

function mountDialog(visible: boolean) {
  return mountWithApp(MadeItemHistoryDialog, {
    props: { visible, item },
  })
}

describe('MadeItemHistoryDialog', () => {
  it('loads the item’s demands and lots when opened', async () => {
    const wrapper = mountDialog(false)
    expect(get).not.toHaveBeenCalled()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(2)
    // Both lists are scoped to this item: the dialog must never show another
    // item's production record.
    expect(get.mock.calls.map((call) => [call[0], call[1]?.params?.made_item_id])).toEqual([
      ['/made-items-demands', 1],
      ['/production-lots/', 1],
    ])

    const text = document.body.textContent ?? ''
    expect(text).toContain('L-2026-011')
    expect(text).toContain('P-100')
  })
})
