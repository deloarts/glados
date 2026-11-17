import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandPipelinePanel from '../DemandPipelinePanel.vue'

function mountPanel(props: Record<string, unknown> = {}) {
  return mountWithApp(DemandPipelinePanel, {
    props: { madeCounts: {}, boughtCounts: {}, sourceCounts: {}, loading: false, ...props },
  })
}

describe('DemandPipelinePanel', () => {
  it('draws one segment per moving status and names the fulfilled count of each kind', () => {
    const wrapper = mountPanel({
      boughtCounts: { open: 2, allocated: 0, ordered: 5, fulfilled: 7, canceled: 1 },
      madeCounts: { open: 1 },
    })

    const rows = wrapper.findAll('.pipeline-row')
    expect(rows).toHaveLength(3)
    expect(rows[0]?.text()).toContain('0 fulfilled')
    expect(rows[1]?.text()).toContain('7 fulfilled')
    const bought = rows[1]!.findAll('.pipeline-segment')
    expect(bought.map((segment) => segment.attributes('style'))).toEqual([
      expect.stringContaining('flex-grow: 2'),
      expect.stringContaining('flex-grow: 5'),
    ])
    expect(rows[2]?.find('.pipeline-bar-empty').exists()).toBe(true)

    wrapper.unmount()
  })
})
