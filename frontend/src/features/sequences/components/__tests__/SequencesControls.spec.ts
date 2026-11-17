import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import SequencesControls from '../SequencesControls.vue'

function mountControls(permissions: string[], productArchived = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions, is_systemuser: false } as never
  return mountWithApp(SequencesControls, {
    pinia,
    props: { productArchived },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('SequencesControls', () => {
  it('offers New Sequence with write:sequences', () => {
    const wrapper = mountControls(['write:sequences'])
    expect(wrapper.find('[data-testid="sequence-create"]').attributes('disabled')).toBeUndefined()
  })

  it('shows New Sequence disabled without the permission or on an archived product', () => {
    expect(mountControls([]).find('[data-testid="sequence-create"]').attributes('disabled')).toBeDefined()
    expect(
      mountControls(['write:sequences'], true).find('[data-testid="sequence-create"]').attributes('disabled'),
    ).toBeDefined()
  })
})
