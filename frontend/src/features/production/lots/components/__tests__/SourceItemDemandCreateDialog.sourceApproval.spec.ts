import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

// Same harness as the existing SourceItemDemandCreateDialog.spec.ts.

const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()
const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import SourceItemDemandCreateDialog from '../SourceItemDemandCreateDialog.vue'
import LotSelect from '../LotSelect.vue'

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    quantity: 5,
    made_item_revision: '0',
    made_item_material: 'S235',
    source_item_id: 7,
    source_label: 'Stock',
    demand_status: 'open',
    project_id: 100,
    project_number: 'P-1',
    project_customer: 'ACME',
    ...overrides,
  })
}

async function openDialog(props: Record<string, unknown> = {}) {
  const wrapper = mountWithApp(SourceItemDemandCreateDialog, {
    attachTo: document.body,
    props: { visible: false, ...props },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

async function clickSave(wrapper: ReturnType<typeof mount>) {
  await wrapper.findAllComponents({ name: 'Button' }).at(-1)!.trigger('click')
  await flushPromises()
}

function selectLot(wrapper: ReturnType<typeof mount>, lot: LotSummaryResponse) {
  return wrapper.findComponent(LotSelect).vm.$emit('update:modelValue', lot)
}

describe('SourceItemDemandCreateDialog source approval (picker mode)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 50, skip: 0 } })
    postMock.mockResolvedValue({ data: { id: 1 } })
  })

  it('selecting a pending lot shows the warning and disables Save', async () => {
    const wrapper = await openDialog()

    selectLot(wrapper, makeLot({ id: 9, source_approval_status: 'pending' }))
    await flushPromises()

    const message = wrapper.findComponent({ name: 'Message' })
    expect(message.exists()).toBe(true)
    expect(message.props('severity')).toBe('warn')
    expect(message.text()).toBe(
      i18n.global.t('production.lots.detail.record.sourceApproval.noDemandUntilApproved') as string,
    )

    const saveButton = wrapper.findAllComponents({ name: 'Button' }).at(-1)!
    expect(saveButton.attributes('disabled')).toBeDefined()

    await clickSave(wrapper)
    expect(postMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('selecting a rejected lot shows the warning and disables Save too', async () => {
    const wrapper = await openDialog()

    selectLot(
      wrapper,
      makeLot({ id: 9, source_approval_status: 'rejected', source_rejection_reason: 'Bad batch' }),
    )
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(true)
    expect(wrapper.findAllComponents({ name: 'Button' }).at(-1)!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('selecting a not_required lot shows no warning and leaves Save enabled', async () => {
    const wrapper = await openDialog()

    selectLot(wrapper, makeLot({ id: 9, source_approval_status: 'not_required' }))
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(false)
    expect(wrapper.findAllComponents({ name: 'Button' }).at(-1)!.attributes('disabled')).toBeUndefined()

    await clickSave(wrapper)
    expect(postMock).toHaveBeenCalledWith(
      '/source-item-demands',
      expect.objectContaining({ lot_id: 9 }),
    )

    wrapper.unmount()
  })

  // approved is demandable too (see lotSourceEligibility's canDemandSourceItem);
  // only pending/rejected block.
  it('selecting an approved lot shows no warning and leaves Save enabled', async () => {
    const wrapper = await openDialog()

    selectLot(wrapper, makeLot({ id: 9, source_approval_status: 'approved' }))
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(false)
    expect(wrapper.findAllComponents({ name: 'Button' }).at(-1)!.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })
})
