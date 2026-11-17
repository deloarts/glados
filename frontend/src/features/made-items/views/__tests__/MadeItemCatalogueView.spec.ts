import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useMadeItemsCatalogueEditStore } from '../../stores/madeItemsCatalogueEditStore'
import { useMadeItemsStore } from '../../stores/madeItemsStore'

import type { PdmPreviewResponse } from '@/shared/pdm-preview/api'

const fetchPdmPreviewMock = vi.fn<(kind: 'made' | 'bought') => Promise<PdmPreviewResponse>>()

vi.mock('@/shared/pdm-preview/api', () => ({
  fetchPdmPreview: (kind: 'made' | 'bought') => fetchPdmPreviewMock(kind),
}))

import MadeItemCatalogueView from '../MadeItemCatalogueView.vue'

function pdmResponse(overrides: Partial<PdmPreviewResponse> = {}): PdmPreviewResponse {
  return { kind: 'made', enabled: false, unlinked: [], newer: [], ...overrides }
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mountWithApp(MadeItemCatalogueView, {
    pinia,
    global: {
      stubs: {
        MadeItemsCatalogueControls: true,
        MadeItemsCatalogueViews: true,
        MadeItemsCatalogueTable: true,
        MadeItemsCatalogueEdit: true,
      },
    },
  })
  return { pinia, wrapper }
}

describe('MadeItemCatalogueView', () => {
  beforeEach(() => {
    fetchPdmPreviewMock.mockReset()
    fetchPdmPreviewMock.mockResolvedValue(pdmResponse())
  })

  it('renders the catalogue table', () => {
    const { wrapper } = mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'MadeItemsCatalogueTable' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it("loads the PDM preview for 'made' on mount", async () => {
    const { wrapper } = mountView()
    await flushPromises()

    expect(fetchPdmPreviewMock).toHaveBeenCalledWith('made')
    expect(fetchPdmPreviewMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it("reloads the PDM preview whenever the catalogue table's own refresh fires", async () => {
    const { pinia, wrapper } = mountView()
    await flushPromises()
    fetchPdmPreviewMock.mockClear()

    setActivePinia(pinia)
    useMadeItemsStore().triggerRefresh()
    await flushPromises()

    expect(fetchPdmPreviewMock).toHaveBeenCalledWith('made')

    wrapper.unmount()
  })

  it('shows the edit panel only while the catalogue edit store is in edit mode', async () => {
    const { pinia, wrapper } = mountView()
    expect(wrapper.findComponent({ name: 'MadeItemsCatalogueEdit' }).exists()).toBe(false)

    setActivePinia(pinia)
    useMadeItemsCatalogueEditStore().editMode = true
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'MadeItemsCatalogueEdit' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows the PDM preview panel, for the made kind, once the controls bar asks for it', async () => {
    const { wrapper } = mountView()
    expect(wrapper.findComponent({ name: 'PdmPreviewPanel' }).exists()).toBe(false)

    await wrapper.findComponent({ name: 'MadeItemsCatalogueControls' }).vm.$emit('toggle-pdm-preview')

    const panel = wrapper.findComponent({ name: 'PdmPreviewPanel' })
    expect(panel.exists()).toBe(true)
    expect(panel.props('kind')).toBe('made')

    wrapper.unmount()
  })
})
