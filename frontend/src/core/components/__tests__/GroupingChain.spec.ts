import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import GroupingChain from '../GroupingChain.vue'

const items = [
  { id: 1, label: 'Sawing', sublabel: '#1' },
  { id: 2, label: 'Milling', sublabel: '#2' },
  { id: 3, label: 'Drilling', sublabel: '#3' },
]

describe('GroupingChain', () => {
  it('renders one chip per item and a toggle between each adjacent pair', () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: { items, boundaries: new Set<number>() },
    })

    expect(wrapper.findAll('.step-chip')).toHaveLength(3)
    expect(wrapper.findAll('.boundary-toggle')).toHaveLength(2)

    wrapper.unmount()
  })

  it('gives every boundary toggle an accessible name', () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: { items, boundaries: new Set<number>() },
    })

    const toggles = wrapper.findAll('.boundary-toggle')
    expect(toggles.length).toBeGreaterThan(0)
    for (const toggle of toggles) {
      expect(toggle.attributes('aria-label')).toBe('Toggle boundary')
    }

    wrapper.unmount()
  })

  it('toggling a linked boundary emits it as split', async () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: { items, boundaries: new Set<number>() },
    })

    await wrapper.findAll('.boundary-toggle')[0]!.trigger('click')

    expect(wrapper.emitted('update:boundaries')?.[0]?.[0]).toEqual(new Set([2]))

    wrapper.unmount()
  })

  it('toggling an already-split boundary emits it as linked again', async () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: { items, boundaries: new Set([2]) },
    })

    await wrapper.findAll('.boundary-toggle')[0]!.trigger('click')

    expect(wrapper.emitted('update:boundaries')?.[0]?.[0]).toEqual(new Set<number>())

    wrapper.unmount()
  })

  it('disables the toggles and blocks clicks when readonly', async () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: { items, boundaries: new Set<number>(), readonly: true },
    })

    const toggle = wrapper.findAll('.boundary-toggle')[0]!
    expect(toggle.attributes('disabled')).toBeDefined()

    await toggle.trigger('click')
    expect(wrapper.emitted('update:boundaries')).toBeUndefined()

    wrapper.unmount()
  })

  it('renders nothing for an empty item list', () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: { items: [], boundaries: new Set<number>() },
    })

    expect(wrapper.find('.grouping-chain').exists()).toBe(false)

    wrapper.unmount()
  })

  it('offers no toggle on either side of a non-groupable item', () => {
    // A QA inspection in the middle: both of its boundaries are facts, not
    // choices, so they render as plain markers rather than controls.
    const wrapper = mountWithApp(GroupingChain, {
      props: {
        items: [items[0]!, { id: 2, label: 'Measurement', groupable: false }, items[2]!],
        boundaries: new Set([2, 3]),
      },
    })

    expect(wrapper.findAll('.boundary-toggle')).toHaveLength(0)
    expect(wrapper.findAll('.boundary-fixed')).toHaveLength(2)
    expect(wrapper.findAll('.step-chip--standalone')).toHaveLength(1)

    wrapper.unmount()
  })

  it('keeps toggling the groupable pairs around a non-groupable tail item', async () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: {
        items: [items[0]!, items[1]!, { id: 3, label: 'Measurement', groupable: false }],
        boundaries: new Set([3]),
      },
    })

    const toggles = wrapper.findAll('.boundary-toggle')
    expect(toggles).toHaveLength(1)
    await toggles[0]!.trigger('click')

    expect(wrapper.emitted('update:boundaries')?.[0]?.[0]).toEqual(new Set([3, 2]))

    wrapper.unmount()
  })

  it('renders the item icon on a chip that has one', () => {
    const wrapper = mountWithApp(GroupingChain, {
      props: {
        items: [{ id: 1, label: 'Measurement', groupable: false, icon: 'mdi mdi-check-decagram' }],
        boundaries: new Set<number>(),
      },
    })

    const icon = wrapper.find('.step-chip-method i')
    expect(icon.exists()).toBe(true)
    expect(icon.classes()).toContain('mdi-check-decagram')

    wrapper.unmount()
  })

  describe('chipLayout', () => {
    it('defaults to compact: #n below the name, one meta line, no regular-only markup', () => {
      const wrapper = mountWithApp(GroupingChain, {
        props: {
          items: [{ id: 1, label: 'Sawing', sublabel: '#1', meta: 'Setup [min]: 5 · Per Piece [min]: 2' }],
          boundaries: new Set<number>(),
        },
      })

      expect(wrapper.find('.step-chip').classes()).not.toContain('step-chip--regular')
      expect(wrapper.find('.step-chip-title').exists()).toBe(false)
      expect(wrapper.find('.step-chip-seq').text()).toBe('#1')
      expect(wrapper.find('.step-chip-meta').text()).toBe('Setup [min]: 5 · Per Piece [min]: 2')
      expect(wrapper.findAll('.step-chip-meta-line')).toHaveLength(0)

      wrapper.unmount()
    })

    it('explicit chipLayout: "compact" renders exactly like the default', () => {
      const wrapper = mountWithApp(GroupingChain, {
        props: {
          items: [{ id: 1, label: 'Sawing', sublabel: '#1' }],
          boundaries: new Set<number>(),
          chipLayout: 'compact',
        },
      })

      expect(wrapper.find('.step-chip').classes()).not.toContain('step-chip--regular')
      expect(wrapper.find('.step-chip-title').exists()).toBe(false)

      wrapper.unmount()
    })

    it('"regular" renders the number before the name, on one line, and one row per meta line', () => {
      const wrapper = mountWithApp(GroupingChain, {
        props: {
          items: [
            { id: 1, label: 'Sawing', sublabel: '#1', metaLines: ['Setup [min]: 5', 'Per Piece [min]: 2'] },
          ],
          boundaries: new Set<number>(),
          chipLayout: 'regular',
        },
      })

      const chip = wrapper.find('.step-chip')
      expect(chip.classes()).toContain('step-chip--regular')

      // #n sits before the name inside one title line.
      const title = chip.find('.step-chip-title')
      expect(title.exists()).toBe(true)
      const titleChildren = title.findAll('span')
      expect(titleChildren[0]!.classes()).toContain('step-chip-seq')
      expect(titleChildren[0]!.text()).toBe('#1')
      expect(titleChildren[1]!.classes()).toContain('step-chip-method')
      expect(titleChildren[1]!.text()).toContain('Sawing')
      expect(/#1.*Sawing/.test(title.text())).toBe(true)

      // Each meta line is its own element, not one joined string.
      const lines = chip.findAll('.step-chip-meta-line')
      expect(lines).toHaveLength(2)
      expect(lines[0]!.text()).toBe('Setup [min]: 5')
      expect(lines[1]!.text()).toBe('Per Piece [min]: 2')
      expect(chip.find('.step-chip-meta').exists()).toBe(false)

      wrapper.unmount()
    })

    it('"regular" falls back to rendering a lone meta string as a single line when metaLines is unset', () => {
      const wrapper = mountWithApp(GroupingChain, {
        props: {
          items: [{ id: 1, label: 'Sawing', meta: 'Setup [min]: 5 · Per Piece [min]: 2' }],
          boundaries: new Set<number>(),
          chipLayout: 'regular',
        },
      })

      const lines = wrapper.findAll('.step-chip-meta-line')
      expect(lines).toHaveLength(1)
      expect(lines[0]!.text()).toBe('Setup [min]: 5 · Per Piece [min]: 2')

      wrapper.unmount()
    })

    it('"regular" still separates a non-groupable chip with no toggle on either side', () => {
      const wrapper = mountWithApp(GroupingChain, {
        props: {
          items: [items[0]!, { id: 2, label: 'Measurement', groupable: false }, items[2]!],
          boundaries: new Set([2, 3]),
          chipLayout: 'regular',
        },
      })

      expect(wrapper.findAll('.boundary-toggle')).toHaveLength(0)
      expect(wrapper.findAll('.boundary-fixed')).toHaveLength(2)
      expect(wrapper.findAll('.step-chip--standalone')).toHaveLength(1)

      wrapper.unmount()
    })
  })
})
