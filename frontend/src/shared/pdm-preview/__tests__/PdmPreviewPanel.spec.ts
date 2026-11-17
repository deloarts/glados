import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { usePdmPreviewStore } from '../pdmPreviewStore'
import PdmPreviewPanel from '../PdmPreviewPanel.vue'

import type { PdmPreviewFileResponse } from '../api'

function makeFile(overrides: Partial<PdmPreviewFileResponse> = {}): PdmPreviewFileResponse {
  return {
    file_id: 1,
    name: 'Bracket.SLDPRT',
    path: '\\Made-Parts\\Bracket.SLDPRT',
    part_number: 'CAD-1',
    revision: 'A',
    article_name: 'Bracket',
    version: 2,
    state: 'Released',
    modified_at: null,
    sync_state: 'skipped',
    last_error: null,
    ...overrides,
  }
}

describe('PdmPreviewPanel', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  function mountPanel(kind: 'made' | 'bought' = 'made') {
    return mountWithApp(PdmPreviewPanel, {
      props: { kind },
      pinia,
      global: { directives: { tooltip: Tooltip } },
    })
  }

  it('renders one row per unlinked file for the given kind', () => {
    const store = usePdmPreviewStore()
    store.state.made.unlinked = [
      makeFile({ file_id: 1, part_number: 'CAD-1' }),
      makeFile({ file_id: 2, part_number: 'CAD-2' }),
    ]
    store.state.bought.unlinked = [makeFile({ file_id: 3, part_number: 'CAD-3' })]

    const wrapper = mountPanel('made')

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('value')).toHaveLength(2)
  })

  it('shows the empty text when there are no unlinked files', () => {
    usePdmPreviewStore()

    const wrapper = mountPanel('made')

    expect(wrapper.text()).toContain('No preview files')
  })

  it('renders part number, revision, article name, file name and version', () => {
    const store = usePdmPreviewStore()
    store.state.made.unlinked = [
      makeFile({
        part_number: 'CAD-42',
        revision: 'B',
        article_name: 'Widget',
        name: 'Widget.SLDPRT',
        version: 7,
      }),
    ]

    const wrapper = mountPanel('made')

    expect(wrapper.text()).toContain('CAD-42')
    expect(wrapper.text()).toContain('B')
    expect(wrapper.text()).toContain('Widget')
    expect(wrapper.text()).toContain('Widget.SLDPRT')
    expect(wrapper.text()).toContain('7')
  })

  it('rows are greyed via the pdm-preview-row class, not selectable, and have no row-click handler', () => {
    const store = usePdmPreviewStore()
    store.state.made.unlinked = [makeFile()]

    const wrapper = mountPanel('made')

    const table = wrapper.findComponent({ name: 'DataTable' })
    const rowClass = table.props('rowClass') as
      | ((data: PdmPreviewFileResponse) => string)
      | undefined
    expect(rowClass?.(makeFile())).toBe('pdm-preview-row')
    expect(table.props('selectionMode')).toBeFalsy()
    expect(table.vm.$attrs['onRow-click']).toBeUndefined()
  })

  it('shows the sync error as the sync-state cell tooltip', () => {
    const store = usePdmPreviewStore()
    store.state.made.unlinked = [
      makeFile({ sync_state: 'error', last_error: 'required fields missing: material' }),
    ]

    const wrapper = mountPanel('made')

    expect(wrapper.find('.sync-error').exists()).toBe(true)
    expect(wrapper.find('.sync-error').text()).toBe('Error')
  })
})
