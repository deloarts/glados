import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useBoughtItemsCatalogueEditStore } from '../../stores/boughtItemsCatalogueEditStore'
import { useBoughtItemsStore } from '../../stores/boughtItemsStore'

import type { PdmPreviewResponse } from '@/shared/pdm-preview/api'

const fetchPdmPreviewMock = vi.fn<(kind: 'made' | 'bought') => Promise<PdmPreviewResponse>>()

vi.mock('@/shared/pdm-preview/api', () => ({
  fetchPdmPreview: (kind: 'made' | 'bought') => fetchPdmPreviewMock(kind),
}))

import BoughtItemCatalogueView from '../BoughtItemCatalogueView.vue'

function pdmResponse(overrides: Partial<PdmPreviewResponse> = {}): PdmPreviewResponse {
  return { kind: 'bought', enabled: false, unlinked: [], newer: [], ...overrides }
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mountWithApp(BoughtItemCatalogueView, {
    pinia,
    global: {
      stubs: {
        BoughtItemsCatalogueControls: true,
        BoughtItemsCatalogueViews: true,
        BoughtItemsCatalogueTable: true,
        BoughtItemsCatalogueEdit: true,
      },
    },
  })
  return { pinia, wrapper }
}

describe('BoughtItemCatalogueView', () => {
  beforeEach(() => {
    fetchPdmPreviewMock.mockReset()
    fetchPdmPreviewMock.mockResolvedValue(pdmResponse())
  })

  it('renders the catalogue table', () => {
    const { wrapper } = mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'BoughtItemsCatalogueTable' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it("loads the PDM preview for 'bought' on mount", async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(fetchPdmPreviewMock).toHaveBeenCalledWith('bought')
    expect(fetchPdmPreviewMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it("reloads the PDM preview whenever the catalogue table's own refresh fires", async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    fetchPdmPreviewMock.mockClear()

    setActivePinia(pinia)
    useBoughtItemsStore().triggerRefresh()
    await flushPromises()

    expect(fetchPdmPreviewMock).toHaveBeenCalledWith('bought')

    wrapper.unmount()
  })

  it('shows the edit panel only while the catalogue edit store is in edit mode', async () => {
    const { pinia, wrapper } = mountView()
    expect(wrapper.findComponent({ name: 'BoughtItemsCatalogueEdit' }).exists()).toBe(false)

    setActivePinia(pinia)
    useBoughtItemsCatalogueEditStore().editMode = true
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'BoughtItemsCatalogueEdit' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows the PDM preview panel, for the bought kind, once the controls bar asks for it', async () => {
    const { wrapper } = mountView()
    expect(wrapper.findComponent({ name: 'PdmPreviewPanel' }).exists()).toBe(false)

    await wrapper.findComponent({ name: 'BoughtItemsCatalogueControls' }).vm.$emit('toggle-pdm-preview')

    const panel = wrapper.findComponent({ name: 'PdmPreviewPanel' })
    expect(panel.exists()).toBe(true)
    expect(panel.props('kind')).toBe('bought')

    wrapper.unmount()
  })
})
