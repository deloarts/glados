import { beforeEach, describe, it, expect, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ComponentPublicInstance } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

// BoughtItemSelect (rendered in the target-select slot) fetches its options on
// mount, here the merge targets the server returns for the item.
const apiGetMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: { get: (url: string) => apiGetMock(url) },
}))

import BoughtItemMergeDialog from '../BoughtItemMergeDialog.vue'
import SharedItemMergeDialog from '@/shared/components/items/ItemMergeDialog.vue'
import type { ItemMergeOperations } from '@/shared/components/items/ItemMergeDialog.vue'
import { useBoughtItemsStore } from '../../stores/boughtItemsStore'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

// ItemMergeDialog is a generic component (`generic="TItem"`), so Vue Test
// Utils cannot infer its instance type from `findComponent(SharedItemMergeDialog)`
// alone and falls back to a plain DOMWrapper; cast the lookup to the
// instance shape it actually renders with here.
type SharedItemMergeDialogInstance = ComponentPublicInstance<{
  item: BoughtItemResponse | null
  operations: ItemMergeOperations<BoughtItemResponse>
  i18nPrefix: string
  itemLabel: (item: BoughtItemResponse) => string
}>

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    part_number: 'PN-1',
    revision: null,
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    order_code_1: 'OC-1',
    order_code_2: null,
    gtin: null,
    ean: null,
    tariff_number: null,
    article_name: 'Hex Bolt',
    article_groups: [],
    data_source: 'WEB',
    mass: 10,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    manufacturer_id: 3,
    manufacturer_name: 'ACME Corp',
    edp_part_id: null,
    edp_synced_at: null,
    pdf_files: [],
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_sync_state: null,
    pdm_synced_at: null,
    product_family: null,
    product_family_id: null,
    vault_id: null,
    ...overrides,
  }
}

describe('BoughtItemMergeDialog (wrapper)', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
    apiGetMock.mockResolvedValue({ data: [] })
  })

  it('renders the shared dialog with the bought-items store, i18n prefix, and order_code_1 label', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const item = makeItem()
    const wrapper = mountWithApp(BoughtItemMergeDialog, {
      pinia,
      props: { visible: true, item },
    })

    const shared = wrapper.findComponent(SharedItemMergeDialog) as unknown as VueWrapper<SharedItemMergeDialogInstance>
    expect(shared.exists()).toBe(true)
    expect(shared.props('item')).toEqual(item)
    expect(shared.props('i18nPrefix')).toBe('boughtItems.catalogue.merge')
    expect(shared.props('itemLabel')(item)).toBe('OC-1')
    expect(shared.props('operations')).toBe(useBoughtItemsStore())

    wrapper.unmount()
  })

  it('renders the BoughtItemSelect in the target-select slot', async () => {
    const wrapper = mountWithApp(BoughtItemMergeDialog, {
      attachTo: document.body,
      props: { visible: true, item: makeItem() },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('offers the merge targets from the server, a refused one disabled with its reason', async () => {
    const target = makeItem({ id: 2, article_name: 'Allowed' })
    const refused = makeItem({ id: 3, article_name: 'Refused' })
    apiGetMock.mockResolvedValue({
      data: [
        { item: target, refusal: null, reactivates: false },
        { item: refused, refusal: 'archived', reactivates: false },
      ],
    })
    const wrapper = mountWithApp(BoughtItemMergeDialog, {
      attachTo: document.body,
      props: { visible: true, item: makeItem({ id: 1 }) },
    })
    await flushPromises()

    expect(apiGetMock).toHaveBeenCalledWith('/bought-items/1/merge-targets')
    const select = wrapper.findComponent({ name: 'BoughtItemSelect' })
    const disabledReason = select.props('disabledReason') as (item: unknown) => string | null
    expect(disabledReason(target)).toBeNull()
    expect(disabledReason(refused)).toContain('archived')

    wrapper.unmount()
  })
})
