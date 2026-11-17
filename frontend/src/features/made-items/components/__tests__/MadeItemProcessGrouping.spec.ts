import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import MadeItemProcessGrouping from '../MadeItemProcessGrouping.vue'
import type { MadeItemProcessResponse } from '../../types/madeItemsResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeProcess(
  id: number,
  position: number,
  groupIndex: number,
  fabricationMethodName: string,
): MadeItemProcessResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-${String(id).padStart(12, '0')}`,
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    creator_id: 1,
    fabrication_method_id: id,
    role: 'fabrication' as const,
    inspection_method_id: null,
    inspection_method_name: null,
    fabrication_method_name: { enGB: fabricationMethodName },
    made_item_id: 1,
    position,
    group_index: groupIndex,
  }
}

function makeInspectionProcess(
  id: number,
  position: number,
  groupIndex: number,
): MadeItemProcessResponse {
  return {
    ...makeProcess(id, position, groupIndex, ''),
    fabrication_method_id: null,
    role: 'inspection' as const,
    inspection_method_id: 1,
    inspection_method_name: { enGB: 'Visual Inspection' },
  } as MadeItemProcessResponse
}

function mountComponent(processes: MadeItemProcessResponse[], readonly = false) {
  return mountWithApp(MadeItemProcessGrouping, {
    props: { itemId: 1, processes, readonly },
  })
}

// For the showTimes/hideHint props, which mountComponent's fixed signature
// doesn't cover.
function mountWithProps(props: {
  processes: MadeItemProcessResponse[]
  readonly?: boolean
  showTimes?: boolean
  hideHint?: boolean
}) {
  return mountWithApp(MadeItemProcessGrouping, {
    props: { itemId: 1, ...props },
  })
}

describe('MadeItemProcessGrouping', () => {
  it('initializes boundaries from group_index runs', () => {
    const wrapper = mountComponent([
      makeProcess(1, 0, 0, 'Sawing'),
      makeProcess(2, 1, 1, 'Bluing'),
      makeProcess(3, 2, 1, 'Heat Treating'),
    ])

    // 2 groups: [Sawing] and [Bluing, Heat Treatment]: one split toggle
    // and one linked toggle.
    const toggles = wrapper.findAll('.boundary-toggle')
    expect(toggles).toHaveLength(2)
    expect(toggles[0]!.find('i').classes()).toContain('mdi-arrow-split-vertical')
    expect(toggles[1]!.find('i').classes()).toContain('mdi-link')
    expect(wrapper.text()).toContain('2 groups')

    wrapper.unmount()
  })

  it('re-initializes when the processes prop changes (add/delete/reorder in the editor above)', async () => {
    const wrapper = mountComponent([
      makeProcess(1, 0, 0, 'Sawing'),
      makeProcess(2, 1, 1, 'Bluing'),
    ])
    expect(wrapper.text()).toContain('2 groups')

    await wrapper.setProps({
      processes: [makeProcess(1, 0, 0, 'Sawing'), makeProcess(2, 1, 0, 'Bluing')],
    })

    expect(wrapper.text()).toContain('1 group')

    wrapper.unmount()
  })

  // No Save/Reset buttons of its own: the host dialog (MadeItemDetailDialog /
  // MadeItemCreateForm) drives save()/reset()/isDirty via the exposed API,
  // through its own footer buttons.
  it('toggling a boundary, then calling the exposed save(), sends the new grouping and emits the result', async () => {
    putMock.mockResolvedValueOnce({
      data: [
        makeProcess(1, 0, 0, 'Sawing'),
        makeProcess(2, 1, 1, 'Bluing'),
        makeProcess(3, 2, 2, 'Heat Treating'),
      ],
    })

    const wrapper = mountComponent([
      makeProcess(1, 0, 0, 'Sawing'),
      makeProcess(2, 1, 1, 'Bluing'),
      makeProcess(3, 2, 1, 'Heat Treating'),
    ])

    // Split the previously-linked pair apart -> 3 groups.
    await wrapper.findAll('.boundary-toggle')[1]!.trigger('click')
    expect(wrapper.text()).toContain('3 groups')
    expect(wrapper.vm.isDirty).toBe(true)

    await wrapper.vm.save()
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/made-items/1/processes/regroup', {
      groups: [[1], [2], [3]],
    })
    expect(wrapper.emitted('updated')?.[0]?.[0]).toEqual([
      makeProcess(1, 0, 0, 'Sawing'),
      makeProcess(2, 1, 1, 'Bluing'),
      makeProcess(3, 2, 2, 'Heat Treating'),
    ])

    wrapper.unmount()
  })

  it('the exposed reset() restores the boundaries from the last saved processes', async () => {
    const wrapper = mountComponent([
      makeProcess(1, 0, 0, 'Sawing'),
      makeProcess(2, 1, 1, 'Bluing'),
      makeProcess(3, 2, 1, 'Heat Treating'),
    ])

    await wrapper.findAll('.boundary-toggle')[1]!.trigger('click')
    expect(wrapper.text()).toContain('3 groups')

    wrapper.vm.reset()
    await flushPromises()

    expect(wrapper.text()).toContain('2 groups')
    expect(wrapper.vm.isDirty).toBe(false)

    wrapper.unmount()
  })

  it('shows the empty state and no toggles when there are no processes', () => {
    const wrapper = mountComponent([])

    expect(wrapper.text()).toContain('No process steps to group.')
    expect(wrapper.findAll('.boundary-toggle')).toHaveLength(0)

    wrapper.unmount()
  })

  it('has no Save/Reset buttons of its own, and disables toggles when readonly', () => {
    const wrapper = mountComponent(
      [makeProcess(1, 0, 0, 'Sawing'), makeProcess(2, 1, 1, 'Bluing')],
      true,
    )

    expect(wrapper.findAllComponents({ name: 'Button' })).toHaveLength(0)
    expect(wrapper.findAll('.boundary-toggle')[0]!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('excludes an inspection process from grouping - no toggle on either side of it', () => {
    const wrapper = mountComponent([
      makeProcess(1, 0, 0, 'Sawing'),
      makeInspectionProcess(2, 1, 1),
      makeProcess(3, 2, 2, 'Heat Treating'),
    ])

    // Both neighbours of the inspection are separated by a plain marker,
    // leaving no toggle anywhere in this chain.
    expect(wrapper.findAll('.boundary-toggle')).toHaveLength(0)
    expect(wrapper.findAll('.boundary-fixed')).toHaveLength(2)
    expect(wrapper.findAll('.step-chip--standalone')).toHaveLength(1)

    wrapper.unmount()
  })

  it('does not render a times line per chip by default (showTimes unset)', () => {
    const wrapper = mountComponent([makeProcess(1, 0, 0, 'Sawing')])

    expect(wrapper.find('.step-chip-meta').exists()).toBe(false)

    wrapper.unmount()
  })

  it("shows each chip's setup/per-piece minutes as two separate lines when showTimes is set, reusing the routing table's labels", () => {
    const wrapper = mountWithProps({
      processes: [
        {
          ...makeProcess(1, 0, 0, 'Sawing'),
          estimated_setup_minutes: 5,
          estimated_minutes_per_piece: 2.5,
        },
      ],
      showTimes: true,
    })

    const lines = wrapper.findAll('.step-chip-meta-line')
    expect(lines).toHaveLength(2)
    expect(lines[0]!.text()).toContain('Setup [min]')
    expect(lines[0]!.text()).toContain('5')
    expect(lines[1]!.text()).toContain('Per Piece [min]')
    expect(lines[1]!.text()).toContain('2.5')
    // showTimes also switches the chip to the 'regular' GroupingChain
    // layout, leaving no compact-only `.step-chip-meta` element behind.
    expect(wrapper.find('.step-chip-meta').exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows a dash placeholder in the times lines for a chip with unset setup/per-piece minutes', () => {
    const wrapper = mountWithProps({
      processes: [makeProcess(1, 0, 0, 'Sawing')],
      showTimes: true,
    })

    const lines = wrapper.findAll('.step-chip-meta-line')
    expect(lines).toHaveLength(2)
    expect(lines[0]!.text()).toContain('-')
    expect(lines[1]!.text()).toContain('-')

    wrapper.unmount()
  })

  it('showTimes switches the chip to the regular GroupingChain layout - #n to the left of the name', () => {
    const wrapper = mountWithProps({
      processes: [makeProcess(1, 0, 0, 'Sawing')],
      showTimes: true,
    })

    expect(wrapper.find('.step-chip').classes()).toContain('step-chip--regular')
    const title = wrapper.find('.step-chip-title')
    expect(title.exists()).toBe(true)
    expect(/#1.*Sawing/.test(title.text())).toBe(true)

    wrapper.unmount()
  })

  it('without showTimes the chip keeps the compact GroupingChain layout', () => {
    const wrapper = mountComponent([makeProcess(1, 0, 0, 'Sawing')])

    expect(wrapper.find('.step-chip').classes()).not.toContain('step-chip--regular')
    expect(wrapper.find('.step-chip-title').exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows the "Process Grouping" heading and the group-count caption by default (hideHint unset)', () => {
    const wrapper = mountComponent([makeProcess(1, 0, 0, 'Sawing')])

    expect(wrapper.find('.grouping-header').exists()).toBe(true)
    expect(wrapper.find('.grouping-summary').exists()).toBe(true)
    expect(wrapper.text()).toContain('Process Grouping')

    wrapper.unmount()
  })

  it('hides the heading and caption when hideHint is set, without hiding the chips', () => {
    const wrapper = mountWithProps({
      processes: [makeProcess(1, 0, 0, 'Sawing'), makeProcess(2, 1, 1, 'Bluing')],
      hideHint: true,
    })

    expect(wrapper.find('.grouping-header').exists()).toBe(false)
    expect(wrapper.find('.grouping-summary').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Process Grouping')
    expect(wrapper.text()).not.toContain('carried over')
    expect(wrapper.findAll('.step-chip')).toHaveLength(2)

    wrapper.unmount()
  })

  it('keeps readonly behaviour unchanged with showTimes and hideHint combined (no Save/Reset, disabled toggles)', () => {
    const wrapper = mountWithProps({
      processes: [
        {
          ...makeProcess(1, 0, 0, 'Sawing'),
          estimated_setup_minutes: 5,
          estimated_minutes_per_piece: 2,
        },
        makeProcess(2, 1, 1, 'Bluing'),
      ],
      readonly: true,
      showTimes: true,
      hideHint: true,
    })

    expect(wrapper.findAllComponents({ name: 'Button' })).toHaveLength(0)
    expect(wrapper.findAll('.boundary-toggle')[0]!.attributes('disabled')).toBeDefined()
    // 2 chips x 2 lines (setup, per piece) each.
    expect(wrapper.findAll('.step-chip-meta-line')).toHaveLength(4)
    expect(wrapper.find('.grouping-header').exists()).toBe(false)

    wrapper.unmount()
  })
})
