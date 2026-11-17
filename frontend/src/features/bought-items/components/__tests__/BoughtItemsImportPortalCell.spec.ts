import { describe, it, expect, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { BoughtItemImportResult } from '../../types/boughtItemsImportTypes'

vi.mock('../../api/boughtItemsEdpApi', () => ({
  getEdpPartPicture: vi.fn<() => Promise<Blob | null>>().mockResolvedValue(null),
}))

import BoughtItemsImportPortalCell from '../BoughtItemsImportPortalCell.vue'

function result(overrides: Partial<BoughtItemImportResult>): BoughtItemImportResult {
  return { row_index: 0, row_status: 'ready', ...overrides } as BoughtItemImportResult
}

function mountCell(props: { result: BoughtItemImportResult | undefined; fromFile: boolean }) {
  setActivePinia(createPinia())
  return mountWithApp(BoughtItemsImportPortalCell, { props })
}

describe('BoughtItemsImportPortalCell', () => {
  it('offers creating a part the portal does not know from the file', async () => {
    const wrapper = mountCell({ result: result({ row_status: 'not_found' }), fromFile: false })

    await wrapper.find('[data-testid="bought-item-import-skip-lookup"]').trigger('click')

    expect(wrapper.emitted('skip')).toHaveLength(1)
  })

  it('pins the chosen candidate of an ambiguous row', () => {
    const candidate = {
      part_id: 3,
      part_number: 'FES.1',
      order_number: '1',
      type_number: null,
      designation: 'Valve',
      manufacturer_code: 'FES',
      manufacturer_name: 'Festo',
      product_family_name: null,
      picture_url: null,
      part_page_url: null,
    }
    const wrapper = mountCell({
      result: result({ row_status: 'ambiguous', candidates: [candidate] }),
      fromFile: false,
    })

    wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 3)

    expect(wrapper.emitted('pin')).toEqual([[3]])
  })

  it('says a row comes from the file', () => {
    const wrapper = mountCell({ result: undefined, fromFile: true })

    expect(wrapper.text()).not.toBe('')
  })
})
