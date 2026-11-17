import { describe, it, expect, afterEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { useSourceItemsCatalogueEditStore } from '../../stores/sourceItemsCatalogueEditStore'

const mounted: VueWrapper[] = []

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(SourceItemCatalogueView, {
    global: {
      plugins: [pinia, i18n],
      stubs: {
        // The table/edit-panel/controls each own their own store and api
        // calls (fetch, columns, etc.), out of scope for this view, which
        // only owns the page shell, the edit-panel toggle, and its resize
        // handle.
        SourceItemsCatalogueControls: true,
        SourceItemsCatalogueViews: true,
        SourceItemsCatalogueTable: true,
        SourceItemsCatalogueEdit: true,
      },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

import SourceItemCatalogueView from '../SourceItemCatalogueView.vue'

describe('SourceItemCatalogueView', () => {
  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  // This view has no fetch of its own: SourceItemsCatalogueTable (stubbed
  // above) owns the load entirely, same as the production-machines views.

  it('hides the edit panel when editMode is off', () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'SourceItemsCatalogueEdit' }).exists()).toBe(false)
    expect(wrapper.find('.resize-handle-ew').exists()).toBe(false)
  })

  it('shows the edit panel at its default width once editMode turns on', async () => {
    const wrapper = mountView()
    useSourceItemsCatalogueEditStore().editMode = true
    await flushPromises()

    const panel = wrapper.findComponent({ name: 'SourceItemsCatalogueEdit' })
    expect(panel.exists()).toBe(true)
    expect(panel.attributes('style')).toContain('width: 352px')
    expect(wrapper.find('.resize-handle-ew').exists()).toBe(true)
  })

  it('widens the edit panel by dragging the resize handle', async () => {
    const wrapper = mountView()
    useSourceItemsCatalogueEditStore().editMode = true
    await flushPromises()

    const handle = wrapper.find('.resize-handle-ew')
    await handle.trigger('mousedown', { clientX: 100 })

    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 150 }))
    await flushPromises()

    const panel = wrapper.findComponent({ name: 'SourceItemsCatalogueEdit' })
    expect(panel.attributes('style')).toContain('width: 402px')

    window.dispatchEvent(new MouseEvent('mouseup'))
    await flushPromises()

    // A move after mouseup must not affect the width: mouseup tears the
    // listeners down.
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 500 }))
    await flushPromises()
    expect(
      wrapper.findComponent({ name: 'SourceItemsCatalogueEdit' }).attributes('style'),
    ).toContain('width: 402px')
  })

  it('never narrows the edit panel below 200px', async () => {
    const wrapper = mountView()
    useSourceItemsCatalogueEditStore().editMode = true
    await flushPromises()

    const handle = wrapper.find('.resize-handle-ew')
    await handle.trigger('mousedown', { clientX: 100 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: -500 }))
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'SourceItemsCatalogueEdit' }).attributes('style'),
    ).toContain('width: 200px')

    window.dispatchEvent(new MouseEvent('mouseup'))
  })
})
