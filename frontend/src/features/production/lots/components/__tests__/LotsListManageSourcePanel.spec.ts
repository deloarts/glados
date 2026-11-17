import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import ConfirmDialog from 'openvue/confirmdialog'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { makeLotSummaryResponse } from '@/test-utils/factories'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'
import { useProductionLotsSourceStore } from '../../stores/productionLotsSourceStore'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'
import type { SourceItemResponse } from '@/features/source-items'

const getMock = vi.fn<() => Promise<unknown>>().mockResolvedValue({
  data: { items: [], total: 0, limit: 20, skip: 0 },
})
const putMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })
const postMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })

vi.mock('@/core/api', () => ({
  default: {
    get: () => getMock(),
    put: (url: string, payload: unknown) => putMock(url, payload),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import LotsListManageSourcePanel from '../LotsListManageSourcePanel.vue'

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    quantity: 5,
    made_item_revision: '0',
    made_item_material: 'S235',
    source_label: 'No source',
    demand_status: 'open',
    project_id: 100,
    project_number: 'P-1',
    project_customer: 'ACME',
    actions: ['switch_source'],
    ...overrides,
  })
}

function makeSourceItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    id: 42,
    public_id: '22222222-2222-2222-2222-222222222222',
    status: 'active',
    deleted: false,
    created: '2026-07-01',
    changed: null,
    type_id: 1,
    type_name: 'Round bar',
    dimension: '100 x 200 x 20',
    material: 'S235',
    mass: null,
    note: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    approver_id: null,
    manufacturer_id: null,
    manufacturer_name: '',
    ...overrides,
  } as SourceItemResponse
}

// Deeply-nested components (e.g. inside MaterialSourceSelect's inline
// create pane) aren't reliably reachable via CSS id selectors; walking the
// component tree by prop `id` instead is robust regardless of nesting.
function findByAttrId(wrapper: ReturnType<typeof mount>, name: string, id: string) {
  const match = wrapper.findAllComponents({ name }).find((c) => c.attributes('id') === id)
  if (!match) throw new Error(`No <${name} id="${id}"> found`)
  return match
}

let activeWrapper: { unmount: () => void } | null = null

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(
    {
      components: { LotsListManageSourcePanel, ConfirmDialog },
      template:
        '<div><ConfirmDialog /><LotsListManageSourcePanel @assigned="$emit(\'assigned\')" /></div>',
    },
    {
      global: {
        plugins: [
          pinia,
          [OpenVue, { theme: { preset: Aura } }],
          ToastService,
          ConfirmationService,
          i18n,
        ],
        stubs: { RouterLink: true },
      },
      attachTo: document.body,
    },
  )
  activeWrapper = wrapper
  return {
    wrapper,
    sourceStore: useProductionLotsSourceStore(),
    lotsStore: useProductionLotsStore(),
  }
}

describe('LotsListManageSourcePanel', () => {
  beforeEach(() => {
    getMock.mockClear()
    putMock.mockClear()
    postMock.mockClear()
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 20, skip: 0 } })
    putMock.mockResolvedValue({ data: {} })
    postMock.mockResolvedValue({ data: {} })
  })

  afterEach(() => {
    activeWrapper?.unmount()
    activeWrapper = null
    document.body.innerHTML = ''
  })

  it('shows the empty state when nothing is selected', () => {
    const { wrapper } = mountPanel()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('batch-applies the chosen source to every selected lot without an open demand', async () => {
    const { wrapper, sourceStore, lotsStore } = mountPanel()
    lotsStore.triggerRefresh = vi.fn<() => void>()
    sourceStore.setSelectedLots([
      makeLot({ id: 1, lot_number: 'LOT-1', input_demand_id: null }),
      makeLot({ id: 2, lot_number: 'LOT-2', input_demand_id: null }),
    ])
    await flushPromises()

    // MaterialSourceSelect starts on the 'source' tab; simulate picking
    // source item #42 through the panel's own state rather than driving
    // SourceItemSelect's internal search UI.
    const materialSourceSelect = wrapper.findComponent({ name: 'MaterialSourceSelect' })
    await materialSourceSelect.vm.$emit('update:modelValue', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
    })
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/production-lots/1/material-source', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
      confirm_replace_demand: false,
      expected_edit_version: expect.any(Number),
    })
    expect(putMock).toHaveBeenCalledWith('/production-lots/2/material-source', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
      confirm_replace_demand: false,
      expected_edit_version: expect.any(Number),
    })
    expect(sourceStore.selectedLots).toHaveLength(0)
    expect(lotsStore.triggerRefresh).toHaveBeenCalled()
    expect(wrapper.emitted('assigned')).toHaveLength(1)
  })

  it('skips a finished lot that offers no source switch and sends only the others', async () => {
    const { wrapper, sourceStore } = mountPanel()
    sourceStore.setSelectedLots([
      makeLot({ id: 1, lot_number: 'LOT-1', input_demand_id: null }),
      makeLot({ id: 2, lot_number: 'LOT-2', input_demand_id: null, actions: [] }),
    ])
    await flushPromises()

    expect(wrapper.findAll('[data-testid="manage-source-skipped"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="manage-source-skipped-count"]').text()).toContain('1')

    const materialSourceSelect = wrapper.findComponent({ name: 'MaterialSourceSelect' })
    await materialSourceSelect.vm.$emit('update:modelValue', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
    })
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledTimes(1)
    expect(putMock).toHaveBeenCalledWith('/production-lots/1/material-source', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
      confirm_replace_demand: false,
      expected_edit_version: expect.any(Number),
    })
    expect(sourceStore.selectedLots.map((lot) => lot.id)).toEqual([2])
    expect(wrapper.find('[data-testid="manage-source-error"]').exists()).toBe(false)
  })

  it('keeps failed lots selected and reports an error on partial failure', async () => {
    putMock.mockImplementation((url: string) =>
      url === '/production-lots/1/material-source'
        ? Promise.reject(new Error('boom'))
        : Promise.resolve({ data: {} }),
    )
    const { wrapper, sourceStore } = mountPanel()
    sourceStore.setSelectedLots([
      makeLot({ id: 1, lot_number: 'LOT-1' }),
      makeLot({ id: 2, lot_number: 'LOT-2' }),
    ])
    await flushPromises()

    const materialSourceSelect = wrapper.findComponent({ name: 'MaterialSourceSelect' })
    await materialSourceSelect.vm.$emit('update:modelValue', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
    })
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(sourceStore.selectedLots).toHaveLength(1)
    expect(sourceStore.selectedLots[0]!.id).toBe(1)
    expect(wrapper.find('[data-testid="manage-source-error"]').exists()).toBe(true)
    expect(wrapper.emitted('assigned')).toBeUndefined()
  })

  it('confirms once before replacing an open demand, then submits with confirm_replace_demand: true', async () => {
    const { wrapper, sourceStore } = mountPanel()
    sourceStore.setSelectedLots([
      makeLot({ id: 1, lot_number: 'LOT-1', input_demand_id: 500, demand_status: 'open' }),
    ])
    await flushPromises()

    const materialSourceSelect = wrapper.findComponent({ name: 'MaterialSourceSelect' })
    await materialSourceSelect.vm.$emit('update:modelValue', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
    })
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(putMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('LOT-1')

    const acceptButton = Array.from(document.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('Replace Demand'),
    )
    expect(acceptButton).toBeTruthy()
    acceptButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/production-lots/1/material-source', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
      confirm_replace_demand: true,
      expected_edit_version: expect.any(Number),
    })
  })

  it('creates a source item inline via the switch and applies it to every selected lot', async () => {
    postMock.mockResolvedValue({ data: makeSourceItem({ id: 99 }) })
    const { wrapper, sourceStore } = mountPanel()
    sourceStore.setSelectedLots([
      makeLot({ id: 1, lot_number: 'LOT-1', input_demand_id: null }),
      makeLot({ id: 2, lot_number: 'LOT-2', input_demand_id: null }),
    ])
    await flushPromises()

    const selectButton = wrapper.findComponent({ name: 'SelectButton' })
    await selectButton.vm.$emit('update:modelValue', 'create-source')
    await flushPromises()

    await findByAttrId(wrapper, 'Select', 'msc-type').vm.$emit('update:modelValue', 1)
    await findByAttrId(wrapper, 'InputText', 'msc-material').vm.$emit('update:modelValue', 'S235')
    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '100 × 200 × 20')
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith(
      '/source-items',
      expect.objectContaining({ type_id: 1, material: 'S235', dimension: '100 × 200 × 20' }),
    )
    // The item is created exactly once, not once per selected lot.
    expect(postMock).toHaveBeenCalledTimes(1)
    expect(putMock).toHaveBeenCalledWith('/production-lots/1/material-source', {
      bought_item_id: null,
      source_item_id: 99,
      made_item_id: null,
      confirm_replace_demand: false,
      expected_edit_version: expect.any(Number),
    })
    expect(putMock).toHaveBeenCalledWith('/production-lots/2/material-source', {
      bought_item_id: null,
      source_item_id: 99,
      made_item_id: null,
      confirm_replace_demand: false,
      expected_edit_version: expect.any(Number),
    })
    expect(sourceStore.selectedLots).toHaveLength(0)
  })

  it('reuses an identical existing item instead of creating a duplicate', async () => {
    const existingItem = makeSourceItem({
      id: 42,
      type_id: 1,
      material: 'S235',
      dimension: '100 × 200 × 20',
      manufacturer_id: null,
    })
    getMock.mockResolvedValue({ data: { items: [existingItem], total: 1, limit: 50, skip: 0 } })

    const { wrapper, sourceStore } = mountPanel()
    sourceStore.setSelectedLots([makeLot({ id: 1, lot_number: 'LOT-1', input_demand_id: null })])
    await flushPromises()

    const selectButton = wrapper.findComponent({ name: 'SelectButton' })
    await selectButton.vm.$emit('update:modelValue', 'create-source')
    await flushPromises()

    await findByAttrId(wrapper, 'Select', 'msc-type').vm.$emit('update:modelValue', 1)
    await findByAttrId(wrapper, 'InputText', 'msc-material').vm.$emit('update:modelValue', 'S235')
    const dimensionInput = wrapper.findComponent({ name: 'SourceItemDimensionInput' })
    await dimensionInput.vm.$emit('update:modelValue', '100 × 200 × 20')
    await flushPromises()
    // fetchSimilarItems is debounced.
    await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
    await flushPromises()

    expect(document.querySelector('[data-testid="inline-create-duplicate-notice"]')?.textContent).toContain('will be used instead')
    const confirmButton = wrapper.get('.panel-footer button')
    expect(confirmButton.text()).toBe('Apply')

    await confirmButton.trigger('click')
    await flushPromises()

    expect(postMock).not.toHaveBeenCalled()
    expect(putMock).toHaveBeenCalledWith('/production-lots/1/material-source', {
      bought_item_id: null,
      source_item_id: 42,
      made_item_id: null,
      confirm_replace_demand: false,
      expected_edit_version: expect.any(Number),
    })
  })
})
