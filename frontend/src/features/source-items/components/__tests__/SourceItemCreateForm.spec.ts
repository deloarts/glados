import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { useSourceItemsCatalogueEditStore } from '../../stores/sourceItemsCatalogueEditStore'

import type { SourceItemResponse } from '../../types/sourceItemsResponse'

function makeSourceItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    status: 'active',
    archived: false,
    created: '2026-07-01',
    changed: '2026-07-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    type_id: 1,
    type_name: { enGB: 'Round bar' },
    dimension: '100 × 200 × 20',
    material: 'S235',
    mass: null,
    note: null,
    order_code_1: null,
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    approver_id: null,
    manufacturer_id: null,
    manufacturer_name: '',
    ...overrides,
  }
}

const existingItemsFixture: SourceItemResponse[] = [
  makeSourceItem({ id: 10, dimension: '100 × 200 × 20', material: 'S235' }),
  // Substring-material match the component's client-side filter must drop:
  // the backend's `material` filter is `ilike '%S235%'`, so a search for
  // "S235" would also surface "S235X" if the component didn't post-filter.
  makeSourceItem({ id: 11, dimension: '50 × 50 × 10', material: 'S235X' }),
]

const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()
const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import SourceItemCreateForm from '../SourceItemCreateForm.vue'

function mountForm() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(SourceItemCreateForm, {
    pinia,
    attachTo: document.body,
    props: { visible: true },
  })
  return { wrapper, editStore: useSourceItemsCatalogueEditStore() }
}

// Dialog teleports its content to document.body, so wrapper.get('#id')
// (which only searches the wrapper's own DOM subtree) can't reach it;
// findComponent walks the Vue instance tree instead, which teleporting
// doesn't affect.
function findByAttrId(wrapper: ReturnType<typeof mountForm>['wrapper'], name: string, id: string) {
  const match = wrapper.findAllComponents({ name }).find((c) => c.attributes('id') === id)
  if (!match) throw new Error(`No <${name} id="${id}"> found`)
  return match
}

async function setTypeAndMaterial(
  wrapper: ReturnType<typeof mountForm>['wrapper'],
  material: string,
): Promise<void> {
  await findByAttrId(wrapper, 'Select', 'bi-type').vm.$emit('update:modelValue', 1)
  await findByAttrId(wrapper, 'InputText', 'bi-material').vm.$emit('update:modelValue', material)
  await flushPromises()
  // fetchSimilarItems is debounced.
  await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
  await flushPromises()
}

describe('SourceItemCreateForm', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/source-items') {
        return Promise.resolve({
          data: {
            items: existingItemsFixture,
            total: existingItemsFixture.length,
            limit: 50,
            skip: 0,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
    })
    postMock.mockResolvedValue({ data: makeSourceItem({ id: 99 }) })
  })

  it('renders all fields without errors when opened', async () => {
    const { wrapper } = mountForm()
    await flushPromises()
    await flushPromises()

    expect(document.querySelector('#bi-dimension-shape')).not.toBeNull()
    expect(document.querySelector('#bi-type')).not.toBeNull()
    expect(document.querySelector('#bi-material')).not.toBeNull()
    expect(document.querySelector('#bi-manufacturer')).not.toBeNull()

    wrapper.unmount()
  })

  it('fetches similar items by type + material, showing live substring matches unfiltered', async () => {
    const { wrapper } = mountForm()
    await flushPromises()

    await setTypeAndMaterial(wrapper, 'S235')

    // Both fixtures come back: the table stays a live/broad search (the
    // exact-match narrowing only applies to duplicateItem, not display).
    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('value')).toHaveLength(2)

    wrapper.unmount()
  })

  it('searches as soon as either type or material is filled, not requiring both', async () => {
    const { wrapper } = mountForm()
    await flushPromises()
    getMock.mockClear()

    await findByAttrId(wrapper, 'InputText', 'bi-material').vm.$emit('update:modelValue', 'S235')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith(
      '/source-items',
      expect.objectContaining({ params: expect.objectContaining({ material: 'S235' }) }),
    )
    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('value')).toHaveLength(2)

    wrapper.unmount()
  })

  it('re-runs the search when dimension changes, without requiring type/material to change too', async () => {
    const { wrapper } = mountForm()
    await flushPromises()

    await setTypeAndMaterial(wrapper, 'S235')
    getMock.mockClear()

    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '100 × 200 × 20')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith(
      '/source-items',
      expect.objectContaining({
        params: expect.objectContaining({ type_id: 1, material: 'S235' }),
      }),
    )
    // Critical: once type/material narrow the query, dimension must NOT
    // also be sent as a filter: the backend's dimension match is a literal
    // substring, so filtering by it here would hide a permuted duplicate
    // (stored "100 × 200 × 20" doesn't substring-match a typed
    // "200 × 100 × 20") from duplicateItem's candidate pool.
    const lastCall = getMock.mock.calls[getMock.mock.calls.length - 1]
    expect(lastCall?.[1]?.params).not.toHaveProperty('dimension')

    wrapper.unmount()
  })

  it('searches by dimension alone when type and material are both empty', async () => {
    const { wrapper } = mountForm()
    await flushPromises()
    getMock.mockClear()

    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '100 × 200 × 20')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith(
      '/source-items',
      expect.objectContaining({
        params: expect.objectContaining({ dimension: '100 × 200 × 20' }),
      }),
    )

    wrapper.unmount()
  })

  it('blocks Save and warns when a permuted-dimension duplicate exists', async () => {
    const { wrapper } = mountForm()
    await flushPromises()

    await setTypeAndMaterial(wrapper, 'S235')

    // Same spec as fixture #10 (dimension "100 × 200 × 20"), permuted.
    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '200 × 100 × 20')
    await flushPromises()

    expect(document.querySelector('[data-testid="source-item-duplicate-warning"]')).not.toBeNull()
    const saveButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.text() === 'Save')
    // Button has no declared `disabled` prop; it derives disabled-ness
    // from $attrs.disabled at render time, so assert the rendered DOM
    // attribute rather than a component prop.
    expect(saveButton?.attributes('disabled')).toBeDefined()

    await saveButton!.trigger('click')
    await flushPromises()
    expect(postMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('does not block when the manufacturer differs (null vs set)', async () => {
    const { wrapper } = mountForm()
    await flushPromises()

    await setTypeAndMaterial(wrapper, 'S235')

    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '100 × 200 × 20')
    await findByAttrId(wrapper, 'Select', 'bi-manufacturer').vm.$emit('update:modelValue', 5)
    await flushPromises()

    expect(document.querySelector('[data-testid="source-item-duplicate-warning"]')).toBeNull()
    const saveButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.text() === 'Save')
    expect(saveButton?.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('populates the catalogue edit store and closes when "Edit existing item" is clicked', async () => {
    const { wrapper, editStore } = mountForm()
    await flushPromises()

    await setTypeAndMaterial(wrapper, 'S235')

    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '200 × 100 × 20')
    await flushPromises()

    const editButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.text() === 'Edit existing item')
    await editButton!.trigger('click')
    await flushPromises()

    expect(editStore.editMode).toBe(true)
    expect(editStore.selectedItems).toEqual([existingItemsFixture[0]])
    expect(wrapper.emitted('update:visible')).toContainEqual([false])

    wrapper.unmount()
  })
})
