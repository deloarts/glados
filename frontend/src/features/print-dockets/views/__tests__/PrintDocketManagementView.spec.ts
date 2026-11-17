import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

import PrintDocketManagementView from '../PrintDocketManagementView.vue'

// smoke spec for the View tier, assembled from ManagementCrudShell
// with `showCreate: false`: print-template rows are created at startup,
// one per classifier, never created or deleted, so there is no Create
// button. This proves the shell hides it and instead renders
// PrintTemplateManagementControls' two bulk-action buttons via #extra-controls,
// that the table mounts, and that the edit/preview dialogs still open off
// the table's events. PrintTemplateManagementControls' own confirm/API
// behaviour is tested in its own spec.
function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mountWithApp(PrintDocketManagementView, {
    pinia,
    global: {
      stubs: {
        PrintTemplateManagementTable: true,
        PrintTemplateManagementControls: true,
        PrintTemplateEditorDialog: true,
        PrintTemplatePreviewDialog: true,
      },
    },
  })
}

describe('PrintDocketManagementView', () => {
  it('hides the create button, renders the bulk-action controls and the table', () => {
    const wrapper = mountView()

    expect(
      wrapper.findAllComponents({ name: 'Button' }).some((b) => b.props('icon') === 'mdi mdi-plus'),
    ).toBe(false)
    expect(wrapper.findComponent({ name: 'PrintTemplateManagementControls' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'PrintTemplateManagementTable' }).exists()).toBe(true)
    for (const name of [
      'PrintTemplateManagementControls',
      'PrintTemplateManagementTable',
      'PrintTemplateEditorDialog',
      'PrintTemplatePreviewDialog',
    ]) {
      expect(wrapper.findComponent({ name }).props('kind')).toBe('docket')
    }

    wrapper.unmount()
  })

  it('opens the editor/preview dialogs off the table\'s edit/preview events', async () => {
    const wrapper = mountView()
    const template = { classifier: 'production_order_docket', source: '{}' }

    await wrapper.findComponent({ name: 'PrintTemplateManagementTable' }).vm.$emit('edit', template)
    expect(wrapper.findComponent({ name: 'PrintTemplateEditorDialog' }).props('visible')).toBe(true)
    expect(wrapper.findComponent({ name: 'PrintTemplateEditorDialog' }).props('template')).toEqual(
      template,
    )

    await wrapper.findComponent({ name: 'PrintTemplateManagementTable' }).vm.$emit('preview', template)
    expect(wrapper.findComponent({ name: 'PrintTemplatePreviewDialog' }).props('visible')).toBe(true)
    expect(wrapper.findComponent({ name: 'PrintTemplatePreviewDialog' }).props('template')).toEqual(
      template,
    )

    wrapper.unmount()
  })
})
