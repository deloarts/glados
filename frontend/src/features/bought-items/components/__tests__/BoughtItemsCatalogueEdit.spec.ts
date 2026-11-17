import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useBoughtItemsCatalogueEditStore } from '../../stores/boughtItemsCatalogueEditStore'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    put: vi.fn<() => void>(),
  },
}))

import BoughtItemsCatalogueEdit from '../BoughtItemsCatalogueEdit.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    part_number: 'PN-1',
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    order_code_1: 'OC1',
    order_code_2: 'OC2',
    gtin: '123',
    ean: '456',
    tariff_number: '789',
    article_name: 'Article',
    article_groups: [],
    data_source: 'WEB',
    mass: 100,
    note: 'Note',
    weblink: 'http://example.com',
    successor_item_id: null,
    creator_id: 1,
    creator: {
      id: 1,
      public_id: '22222222-2222-2222-2222-222222222222',
      username: 'creator',
      full_name: 'Creator',
      has_avatar: false,
    },
    manufacturer_id: 1,
    manufacturer_name: 'Manufacturer',
    pdf_files: [],
    edp_part_id: null,
    edp_synced_at: null,
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_sync_state: null,
    pdm_synced_at: null,
    product_family: null,
    product_family_id: null,
    revision: null,
    vault_id: null,
    ...overrides,
  }
}

function mountEdit(pinia: ReturnType<typeof createPinia>) {
  return mountWithApp(BoughtItemsCatalogueEdit, { pinia })
}

describe('BoughtItemsCatalogueEdit', () => {
  it('renders nothing when edit mode is off', () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mountEdit(pinia)

    expect(wrapper.find('.edit-panel').exists()).toBe(false)
  })

  it('shows a "no selection" message when edit mode is on but nothing is selected', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect(wrapper.find('.edit-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('Select one or more items to edit.')
  })

  it('populates fields from a single selected item', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([makeItem({ article_name: 'Widget', order_code_1: 'OC-A' })])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect((wrapper.find('#bie-article-name').element as HTMLInputElement).value).toBe('Widget')
    expect((wrapper.find('#bie-order-code-1').element as HTMLInputElement).value).toBe('OC-A')
  })

  it('shows "Multiple values" only for fields that differ across the selection', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([
      makeItem({ id: 1, article_name: 'Widget', order_code_1: 'SAME' }),
      makeItem({ id: 2, article_name: 'Gadget', order_code_1: 'SAME' }),
    ])

    const wrapper = mountEdit(pinia)
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    const articleNameInput = wrapper.find('#bie-article-name').element as HTMLInputElement
    const orderCode1Input = wrapper.find('#bie-order-code-1').element as HTMLInputElement

    // Differing values: field is empty with a "Multiple values" placeholder.
    expect(articleNameInput.value).toBe('')
    expect(articleNameInput.placeholder).toBe('Multiple values')

    // Same value across both items: field shows that shared value.
    expect(orderCode1Input.value).toBe('SAME')
    expect(orderCode1Input.placeholder).not.toBe('Multiple values')

    expect(logs).toEqual([])
  })

  it('shows the delivery tolerances, the global value where an item has none', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([
      makeItem({ id: 1, over_delivery_tolerance_percent: 5 }),
      makeItem({ id: 2, over_delivery_tolerance_percent: 8 }),
    ])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    const inputs = wrapper
      .findAllComponents({ name: 'InputNumber' })
      .filter((c) => String(c.attributes('id')).includes('delivery_tolerance'))
    const [over, under] = inputs
    expect(over!.props('modelValue')).toBeNull()
    expect(over!.props('placeholder')).toBe('Multiple values')
    expect(under!.props('placeholder')).toBe('As in the settings')
  })
})
