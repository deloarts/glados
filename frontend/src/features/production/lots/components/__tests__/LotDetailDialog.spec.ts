import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

import LotDetailDialog from '../LotDetailDialog.vue'

// Records the drawer's props, so the spec sees which page it opens.
const HelpDrawerStub = defineComponent({
  name: 'HelpDrawer',
  props: { visible: Boolean, slug: String },
  template: '<div />',
})

describe('LotDetailDialog', () => {
  it('opens the lots handbook page from its help button', async () => {
    const wrapper = mountWithApp(LotDetailDialog, {
      attachTo: document.body,
      props: { visible: true, lotId: null },
      global: { stubs: { LotDetailContent: true, HelpDrawer: HelpDrawerStub } },
    })
    await flushPromises()

    const drawer = wrapper.findComponent(HelpDrawerStub)
    expect(drawer.props('slug')).toBe('production/lots')
    expect(drawer.props('visible')).toBe(false)

    const help = document.body.querySelector('[data-testid="lot-dialog-help"]') as HTMLElement
    help.click()
    await flushPromises()

    expect(drawer.props('visible')).toBe(true)
    wrapper.unmount()
  })
})
