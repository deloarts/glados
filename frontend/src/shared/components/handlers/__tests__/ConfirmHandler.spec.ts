import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useConfirm } from 'openvue/useconfirm'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { CONFIRM_DELETE_GROUP } from '@/shared/composables/useConfirmDelete'

import ConfirmHandler from '../ConfirmHandler.vue'

// A view that asks for a confirmation without a ConfirmDialog of its own,
// as every view does now, next to the app's handler.
function mountApp(group?: string) {
  const Asker = defineComponent({
    setup() {
      const confirm = useConfirm()
      return () =>
        h('button', {
          'data-testid': 'ask',
          onClick: () => confirm.require({ group, header: 'Archive?', message: 'Archive it?' }),
        })
    },
  })
  return mountWithApp(
    defineComponent({ render: () => [h(ConfirmHandler), h(Asker)] }),
    { attachTo: document.body },
  )
}

describe('ConfirmHandler', () => {
  it('shows an ungrouped confirmation asked by any view', async () => {
    const wrapper = mountApp()

    await wrapper.get('[data-testid="ask"]').trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Archive it?')
    wrapper.unmount()
  })

  it('shows a delete confirmation once, in its own dialog', async () => {
    const wrapper = mountApp(CONFIRM_DELETE_GROUP)

    await wrapper.get('[data-testid="ask"]').trigger('click')
    await flushPromises()

    expect(document.body.textContent?.split('Archive it?').length).toBe(2)
    wrapper.unmount()
  })
})
