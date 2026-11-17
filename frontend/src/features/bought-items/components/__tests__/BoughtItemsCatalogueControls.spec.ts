import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import BoughtItemsCatalogueControls from '../BoughtItemsCatalogueControls.vue'

import type { PdmPreviewFileResponse } from '@/shared/pdm-preview/api'

function makeFile(fileId: number): PdmPreviewFileResponse {
  return {
    file_id: fileId,
    name: `part-${fileId}.sldprt`,
    path: `\\Bought-Parts\\part-${fileId}.sldprt`,
    part_number: `CAD-${fileId}`,
    revision: null,
    article_name: 'Bolt M6',
    version: 1,
    state: 'Released',
    modified_at: null,
    sync_state: 'skipped',
    last_error: null,
  }
}

// A minimal router is enough for HelpButton's defensive useRoute() call;
// no navigation happens in these specs.
const router = createRouter({ history: createMemoryHistory(), routes: [] })

describe('BoughtItemsCatalogueControls', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  function mountControls() {
    return mountWithApp(BoughtItemsCatalogueControls, {
      pinia,
      global: { plugins: [router] },
    })
  }

  it('shows the PDM preview toggle with the unlinked count when enabled', () => {
    const store = usePdmPreviewStore()
    store.state.bought.enabled = true
    store.state.bought.unlinked = [makeFile(1), makeFile(2), makeFile(3)]

    const wrapper = mountControls()

    const buttons = wrapper.findAllComponents({ name: 'Button' })
    const toggle = buttons.find((b) => b.props('label') === 'PDM Preview (3)')
    expect(toggle).toBeTruthy()
  })

  it('hides the toggle entirely when the PDM preview is disabled', () => {
    const store = usePdmPreviewStore()
    store.state.bought.enabled = false

    const wrapper = mountControls()

    const buttons = wrapper.findAllComponents({ name: 'Button' })
    expect(buttons.some((b) => String(b.props('label') ?? '').startsWith('PDM Preview'))).toBe(
      false,
    )
  })

  it('emits toggle-pdm-preview when the toggle button is clicked', async () => {
    const store = usePdmPreviewStore()
    store.state.bought.enabled = true
    store.state.bought.unlinked = [makeFile(1)]

    const wrapper = mountControls()

    const buttons = wrapper.findAllComponents({ name: 'Button' })
    const toggle = buttons.find((b) => b.props('label') === 'PDM Preview (1)')
    await toggle?.trigger('click')

    expect(wrapper.emitted('toggle-pdm-preview')).toHaveLength(1)
  })

  it('does not mix in the made-items preview count', () => {
    const store = usePdmPreviewStore()
    store.state.made.enabled = true
    store.state.made.unlinked = [makeFile(1), makeFile(2)]
    store.state.bought.enabled = true
    store.state.bought.unlinked = [makeFile(3)]

    const wrapper = mountControls()

    const buttons = wrapper.findAllComponents({ name: 'Button' })
    expect(buttons.some((b) => b.props('label') === 'PDM Preview (1)')).toBe(true)
    expect(buttons.some((b) => b.props('label') === 'PDM Preview (2)')).toBe(false)
  })
})
