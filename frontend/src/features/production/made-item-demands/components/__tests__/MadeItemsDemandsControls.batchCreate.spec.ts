import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useMadeItemsDemandsBatchDraftStore } from '../../stores/madeItemsDemandsBatchDraftStore'

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 20, skip: 0 } }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MadeItemsDemandsControls from '../MadeItemsDemandsControls.vue'
import BatchCreateMadeItemDemandsDialog from '../BatchCreateMadeItemDemandsDialog.vue'
import { useMadeItemsDemandsStore } from '@/features/made-items'

function mountControls(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(MadeItemsDemandsControls, {
    pinia,
    global: {
      stubs: {
        MadeItemDemandCreateForm: true,
        MadeItemsAutoAssignLotsDialog: true,
        BatchCreateMadeItemDemandsDialog: true,
      },
      directives: { tooltip: Tooltip },
    },
  })
}

function batchCreateButton(wrapper: ReturnType<typeof mountControls>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === i18n.global.t('madeItems.demands.controls.batchCreate'))!
}

describe('MadeItemsDemandsControls batch create', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the Batch Create button', async () => {
    const wrapper = mountControls(['write:demand_items'])
    await flushPromises()

    expect(batchCreateButton(wrapper).exists()).toBe(true)

    wrapper.unmount()
  })

  it('disables Batch Create without write:demand_items', async () => {
    const wrapper = mountControls([])
    await flushPromises()

    expect(batchCreateButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('enables Batch Create with write:demand_items and opens the dialog on click', async () => {
    const wrapper = mountControls(['write:demand_items'])
    await flushPromises()

    expect(batchCreateButton(wrapper).attributes('disabled')).toBeUndefined()

    const dialog = wrapper.findComponent(BatchCreateMadeItemDemandsDialog)
    expect(dialog.props('visible')).toBe(false)

    await batchCreateButton(wrapper).trigger('click')

    expect(dialog.props('visible')).toBe(true)

    wrapper.unmount()
  })

  it('shows a badge when the batch draft store has an unfinished draft', async () => {
    const wrapper = mountControls(['write:demand_items'])
    await flushPromises()

    expect(batchCreateButton(wrapper).props('badge')).toBeFalsy()

    const draftStore = useMadeItemsDemandsBatchDraftStore()
    draftStore.addRow({
      row_index: 0,
      project_number: 'PRJ-001',
      quantity: 1,
      part_number: 'PN-1',
      revision: 'A',
      article_name: null,
      desired_delivery_date: null,
      note: null,
    })
    await flushPromises()

    expect(batchCreateButton(wrapper).props('badge')).toBeTruthy()

    wrapper.unmount()
  })

  it('refreshes the demands list once the batch dialog emits created', async () => {
    const wrapper = mountControls(['write:demand_items'])
    await flushPromises()

    const demandsStore = useMadeItemsDemandsStore()
    const before = demandsStore.refreshTrigger

    wrapper.findComponent(BatchCreateMadeItemDemandsDialog).vm.$emit('created')
    await flushPromises()

    expect(demandsStore.refreshTrigger).toBeGreaterThan(before)

    wrapper.unmount()
  })
})
