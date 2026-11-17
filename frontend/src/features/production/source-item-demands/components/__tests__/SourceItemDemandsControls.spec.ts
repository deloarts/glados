import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 20, skip: 0 } }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import SourceItemDemandsControls from '../SourceItemDemandsControls.vue'
import SourceItemDemandCreateDialog from '../../../lots/components/SourceItemDemandCreateDialog.vue'
import { useSourceItemDemandsStore } from '@/features/source-items'

function mountControls(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(SourceItemDemandsControls, {
    pinia,
    global: {
      stubs: { SourceItemDemandCreateDialog: true },
    },
  })
}

function newDemandButton(wrapper: ReturnType<typeof mountControls>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === i18n.global.t('sourceItems.demands.controls.new'))!
}

describe('SourceItemDemandsControls', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('disables New Demand without write:lots', async () => {
    const wrapper = mountControls([])
    await flushPromises()

    expect(newDemandButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('opens the create dialog with write:lots, and no lot pinned', async () => {
    const wrapper = mountControls(['write:lots'])
    await flushPromises()

    const dialog = wrapper.findComponent(SourceItemDemandCreateDialog)
    expect(dialog.props('visible')).toBe(false)

    await newDemandButton(wrapper).trigger('click')

    expect(dialog.props('visible')).toBe(true)
    // No lotId binding -> falls back to the prop default, so the dialog renders
    // its own lot picker.
    expect(dialog.props('lotId')).toBeNull()

    wrapper.unmount()
  })

  it('refreshes the demands list once a demand is created', async () => {
    const wrapper = mountControls(['write:lots'])
    await flushPromises()

    const demandsStore = useSourceItemDemandsStore()
    const before = demandsStore.refreshTrigger

    wrapper.findComponent(SourceItemDemandCreateDialog).vm.$emit('created', { id: 1 })
    await flushPromises()

    expect(demandsStore.refreshTrigger).toBeGreaterThan(before)

    wrapper.unmount()
  })
})
