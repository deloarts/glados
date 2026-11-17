import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'
import type { EdpItemLookup, EdpLookupField } from '../../types/boughtItemsEdpTypes'

const lookupMock = vi.fn<(itemId: number, partId?: number) => Promise<EdpItemLookup>>()
const applyMock =
  vi.fn<(itemId: number, partId: number, fields: EdpLookupField[]) => Promise<BoughtItemResponse>>()

vi.mock('../../api/boughtItemsEdpApi', () => ({
  lookupItemInEdp: (itemId: number, partId?: number) => lookupMock(itemId, partId),
  applyEdpLookup: (itemId: number, partId: number, fields: EdpLookupField[]) =>
    applyMock(itemId, partId, fields),
  getEdpPartPicture: vi.fn<() => Promise<Blob | null>>().mockResolvedValue(null),
}))

import BoughtItemEdpLookupDialog from '../BoughtItemEdpLookupDialog.vue'

const ITEM = { id: 7, article_name: 'Mine' } as BoughtItemResponse

function lookup(overrides: Partial<EdpItemLookup> = {}): EdpItemLookup {
  return {
    item_id: 7,
    part: {
      part_id: 1,
      part_number: 'FES.19210',
      order_number: '19210',
      type_number: null,
      designation: 'Zylinder',
      manufacturer_code: 'FES',
      manufacturer_name: 'Festo',
      product_family_name: null,
      picture_url: null,
      part_page_url: null,
    },
    candidates: [],
    errors: [],
    fields: [
      { field: 'article_name', item_value: 'Mine', portal_value: 'Zylinder', differs: true, applicable: true },
      { field: 'order_code_1', item_value: '19210', portal_value: '19210', differs: false, applicable: false },
      { field: 'manufacturer_id', item_value: 'A', portal_value: 'B', differs: true, applicable: false },
    ],
    ...overrides,
  }
}

async function mountDialog() {
  setActivePinia(createPinia())
  const wrapper = mountWithApp(BoughtItemEdpLookupDialog, {
    props: { item: ITEM, visible: false },
    attachTo: document.body,
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

// The dialog teleports to document.body, so buttons and text are found there.
function button(testId: string): HTMLElement {
  const element = document.body.querySelector<HTMLElement>(`[data-testid="${testId}"]`)
  if (!element) throw new Error(`no ${testId}`)
  return element
}

describe('BoughtItemEdpLookupDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    applyMock.mockResolvedValue(ITEM)
  })

  it('preselects only the applicable fields and applies them', async () => {
    lookupMock.mockResolvedValue(lookup())
    const wrapper = await mountDialog()

    button('edp-lookup-apply').click()
    await flushPromises()

    expect(applyMock).toHaveBeenCalledWith(7, 1, ['article_name'])
    expect(wrapper.emitted('applied')).toBeTruthy()
  })

  it('links without taking fields', async () => {
    lookupMock.mockResolvedValue(lookup())
    await mountDialog()

    button('edp-lookup-link').click()
    await flushPromises()

    expect(applyMock).toHaveBeenCalledWith(7, 1, [])
  })

  it('explains fields PDM owns', async () => {
    lookupMock.mockResolvedValue(lookup())
    await mountDialog()

    expect(document.body.textContent).toContain('SolidWorks')
  })
})
