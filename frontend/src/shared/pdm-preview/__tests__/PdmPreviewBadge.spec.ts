import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import PdmPreviewBadge from '../PdmPreviewBadge.vue'

import type { PdmPreviewNewerResponse } from '../api'

function makePreview(overrides: Partial<PdmPreviewNewerResponse> = {}): PdmPreviewNewerResponse {
  return {
    item_id: 1,
    item_public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    part_number: 'CAD-1',
    revision: 'A',
    file_id: 10,
    name: 'part.sldprt',
    version: 3,
    state: 'Released',
    modified_at: null,
    ...overrides,
  }
}

function mountBadge(preview: PdmPreviewNewerResponse) {
  return mountWithApp(PdmPreviewBadge, {
    props: { preview },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('PdmPreviewBadge', () => {
  it('renders exactly one info-severity Tag with the version and state in its label', () => {
    const wrapper = mountBadge(makePreview({ version: 3, state: 'Released' }))

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    expect(tags).toHaveLength(1)
    expect(tags[0]?.props('value')).toBe('Preview v3 · Released')
    expect(tags[0]?.props('severity')).toBe('info')
  })

  it('interpolates a different version/state pair correctly', () => {
    const wrapper = mountBadge(makePreview({ version: 12, state: 'InWork' }))

    expect(wrapper.findComponent({ name: 'Tag' }).props('value')).toBe('Preview v12 · InWork')
  })

  it('mounts without a modified date (tooltip has nothing to show)', () => {
    const wrapper = mountBadge(makePreview({ modified_at: null }))

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(true)
  })
})
