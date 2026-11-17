import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useMadeItemsCatalogueEditStore } from '../../stores/madeItemsCatalogueEditStore'

import type { MadeItemResponse } from '../../types/madeItemsResponse'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import api from '@/core/api'
import { makeMadeItemResponse } from '@/test-utils/factories'

import MadeItemsCatalogueEdit from '../MadeItemsCatalogueEdit.vue'

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return makeMadeItemResponse({
    public_id: '11111111-1111-1111-1111-111111111111',
    article_name: 'Article',
    mass: 100,
    note: 'Note',
    weblink: 'http://example.com',
    creator: {
      id: 1,
      public_id: '22222222-2222-2222-2222-222222222222',
      username: 'creator',
      full_name: 'Creator',
      has_avatar: false,
    },
    ...overrides,
  })
}

function mountEdit(pinia: ReturnType<typeof createPinia>) {
  return mountWithApp(MadeItemsCatalogueEdit, { pinia })
}

describe('MadeItemsCatalogueEdit', () => {
  it('renders nothing when edit mode is off', () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mountEdit(pinia)

    expect(wrapper.find('.edit-panel').exists()).toBe(false)
  })

  it('shows a "no selection" message when edit mode is on but nothing is selected', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect(wrapper.find('.edit-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('Select one or more items to edit.')
  })

  it('populates fields from a single selected item', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([makeItem({ article_name: 'Widget', part_number: 'PN-9' })])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect((wrapper.find('#mie-article-name').element as HTMLInputElement).value).toBe('Widget')
    expect((wrapper.find('#mie-part-number').element as HTMLInputElement).value).toBe('PN-9')
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

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([
      makeItem({ id: 1, article_name: 'Widget', part_number: 'SAME' }),
      makeItem({ id: 2, article_name: 'Gadget', part_number: 'SAME' }),
    ])

    const wrapper = mountEdit(pinia)
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    const articleNameInput = wrapper.find('#mie-article-name').element as HTMLInputElement
    const partNumberInput = wrapper.find('#mie-part-number').element as HTMLInputElement

    // Differing values: field is empty with a "Multiple values" placeholder.
    expect(articleNameInput.value).toBe('')
    expect(articleNameInput.placeholder).toBe('Multiple values')

    // Same value across both items: field shows that shared value.
    expect(partNumberInput.value).toBe('SAME')
    expect(partNumberInput.placeholder).not.toBe('Multiple values')

    expect(logs).toEqual([])
  })

  it('preserves source_item_id when saving an edit to an unrelated field', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const item = makeItem({ id: 1, source_item_id: 42 })

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([item])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    vi.mocked(api.put).mockResolvedValueOnce({ data: { ...item, article_name: 'Renamed' } })

    await wrapper.find('#mie-article-name').setValue('Renamed')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(api.put).toHaveBeenCalledWith(
      '/made-items/1',
      expect.objectContaining({ source_item_id: 42 }),
    )
  })

  it('disables policy-flagged fields for a WEB selection and shows the shared hint', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'material', web_requires_revision: true },
      { field: 'note', web_requires_revision: false },
    ]

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([makeItem({ data_source: 'WEB' })])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect((wrapper.find('#mie-material').element as HTMLInputElement).disabled).toBe(true)
    expect((wrapper.find('#mie-note').element as HTMLTextAreaElement).disabled).toBe(false)
    expect(wrapper.text()).toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  // ── Granular material-source policy (mirrors MadeItemDetailDialog.spec.ts's
  // own coverage, plus the bulk-only mixed-selection escalation) ───────────

  it('leaves the unflagged half of a split material-source policy fully usable', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: false },
      { field: 'source_item_id', web_requires_revision: true },
    ]

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([
      makeItem({ data_source: 'WEB', bought_item_id: 5, source_item_id: null }),
    ])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect(wrapper.find('.field-locked').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).props('disabled')).toBe(false)
    expect(wrapper.text()).not.toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  it('locks the whole material-source control only once both fields are flagged', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: true },
      { field: 'source_item_id', web_requires_revision: true },
    ]

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([makeItem({ data_source: 'WEB' })])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect(wrapper.find('.field-locked').exists()).toBe(true)
    expect(wrapper.text()).toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  it('locks the toggle conservatively for a mixed selection where a flagged field is set on at least one item', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: false },
      { field: 'source_item_id', web_requires_revision: true },
    ]

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    // Mixed: one item has bought set, the other has the flagged source_item_id
    // set. form.materialSource is nulled out by resetFormFromSelection
    // (mixedFields), which hides the per-item values MaterialSourceSelect
    // would need to judge this itself, so the wrapper locks conservatively.
    editStore.setSelectedItems([
      makeItem({ id: 1, data_source: 'WEB', bought_item_id: 5, source_item_id: null }),
      makeItem({ id: 2, data_source: 'WEB', bought_item_id: null, source_item_id: 99 }),
    ])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect(wrapper.find('.field-locked').exists()).toBe(true)
  })

  it('does not lock the toggle for a mixed selection when no selected item has a flagged field set', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'source_item_id', web_requires_revision: true },
    ]

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([
      makeItem({ id: 1, data_source: 'WEB', bought_item_id: 5, source_item_id: null }),
      makeItem({ id: 2, data_source: 'WEB', bought_item_id: 8, source_item_id: null }),
    ])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect(wrapper.find('.field-locked').exists()).toBe(false)
  })

  it('blocks save client-side when a staged material-source change would violate a flagged field, even if it slipped past the UI', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: false },
      { field: 'source_item_id', web_requires_revision: true },
    ]
    vi.mocked(api.put).mockClear()

    const item = makeItem({ id: 1, data_source: 'WEB', bought_item_id: null, source_item_id: 99 })
    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([item])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    // Force a staged value that changes the flagged source_item_id, bypassing
    // MaterialSourceSelect's own restrictions. The save-diff backstop must
    // still catch it.
    const materialSourceSelect = wrapper.findComponent({ name: 'MaterialSourceSelect' })
    await materialSourceSelect.vm.$emit('update:modelValue', {
      bought_item_id: null,
      source_item_id: 123,
      made_item_id: null,
    })
    await flushPromises()

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(api.put).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  it('does not lock policy fields when every selected item is CAD', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useHostStore().madeItemPartNumbers.revision.field_policy = [
      { field: 'material', web_requires_revision: true },
    ]

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([makeItem({ data_source: 'CAD' })])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    expect((wrapper.find('#mie-material').element as HTMLInputElement).disabled).toBe(false)
    expect(wrapper.text()).not.toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  // Verifies the error-surfacing path (not a toast; this component shows a
  // plain inline Message, see buildPayload/onSubmit's catch block): a
  // rejected save renders the error rather than throwing.
  it('surfaces a rejected save as an inline error message', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems([makeItem({ id: 1 })])

    const wrapper = mountEdit(pinia)
    await flushPromises()

    const conflictError = Object.assign(new Error('Conflict'), {
      isAxiosError: true,
      response: { status: 409, data: { detail: 'Changing this field requires a new revision.' } },
    })
    vi.mocked(api.put).mockRejectedValueOnce(conflictError)

    await wrapper.find('#mie-article-name').setValue('Renamed')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Changing this field requires a new revision.')
  })
})
