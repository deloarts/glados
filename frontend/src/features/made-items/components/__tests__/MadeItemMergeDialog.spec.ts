import { beforeEach, describe, it, expect, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ComponentPublicInstance } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemResponse } from '@/test-utils/factories'

// MadeItemSelect (rendered in the target-select slot) fetches its options on
// mount, here the merge targets the server returns for the item.
const apiGetMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: { get: (url: string) => apiGetMock(url) },
}))

import MadeItemMergeDialog from '../MadeItemMergeDialog.vue'
import SharedItemMergeDialog from '@/shared/components/items/ItemMergeDialog.vue'
import type { ItemMergeOperations } from '@/shared/components/items/ItemMergeDialog.vue'
import { useMadeItemsStore } from '../../stores/madeItemsStore'

import type { MadeItemResponse } from '../../types/madeItemsResponse'

// ItemMergeDialog is a generic component (`generic="TItem"`), so Vue Test
// Utils cannot infer its instance type from `findComponent(SharedItemMergeDialog)`
// alone and falls back to a plain DOMWrapper. Cast the lookup to the
// instance shape it actually renders with here.
type SharedItemMergeDialogInstance = ComponentPublicInstance<{
  item: MadeItemResponse | null
  operations: ItemMergeOperations<MadeItemResponse>
  i18nPrefix: string
  itemLabel: (item: MadeItemResponse) => string
}>

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return makeMadeItemResponse({ revision: 'B', material: 'Steel', ...overrides })
}

describe('MadeItemMergeDialog (wrapper)', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
    apiGetMock.mockResolvedValue({ data: [] })
  })

  it('renders the shared dialog with the made-items store, i18n prefix, and the part-number/revision label', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const item = makeItem({ part_number: 'PN-1', revision: 'B' })
    const wrapper = mountWithApp(MadeItemMergeDialog, {
      pinia,
      props: { visible: true, item },
    })

    const shared = wrapper.findComponent(SharedItemMergeDialog) as unknown as VueWrapper<SharedItemMergeDialogInstance>
    expect(shared.exists()).toBe(true)
    expect(shared.props('item')).toEqual(item)
    expect(shared.props('i18nPrefix')).toBe('madeItems.catalogue.merge')
    expect(shared.props('itemLabel')(item)).toBe('PN-1:B')
    expect(shared.props('operations')).toBe(useMadeItemsStore())

    wrapper.unmount()
  })

  it('renders the MadeItemSelect in the target-select slot', async () => {
    const wrapper = mountWithApp(MadeItemMergeDialog, {
      attachTo: document.body,
      props: { visible: true, item: makeItem() },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'MadeItemSelect' }).exists()).toBe(true)

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
    const wrapper = mountWithApp(MadeItemMergeDialog, {
      attachTo: document.body,
      props: { visible: true, item: makeItem({ id: 1 }) },
    })
    await flushPromises()

    expect(apiGetMock).toHaveBeenCalledWith('/made-items/1/merge-targets')
    const select = wrapper.findComponent({ name: 'MadeItemSelect' })
    const disabledReason = select.props('disabledReason') as (item: unknown) => string | null
    expect(disabledReason(target)).toBeNull()
    expect(disabledReason(refused)).toContain('archived')

    wrapper.unmount()
  })
})
