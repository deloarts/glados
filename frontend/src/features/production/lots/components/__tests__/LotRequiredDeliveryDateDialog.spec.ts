import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'
import type { LotUpdateRequest } from '../../../types/productionLotsRequest'

const updateMock =
  vi.fn<(id: number, payload: LotUpdateRequest) => Promise<LotSummaryResponse>>()
vi.mock('../../../stores/productionLotsStore', () => ({
  useProductionLotsStore: () => ({ update: updateMock }),
}))

import LotRequiredDeliveryDateDialog from '../LotRequiredDeliveryDateDialog.vue'

/**
 * Structural, matching how useLotsTableDialogs types its own template ref,
 * so the test drives the dialog the same way its real caller does.
 */
interface LotRequiredDeliveryDateDialogVm {
  open(lot: LotSummaryResponse): void
}

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({
    id: 7,
    public_id: '77777777-7777-7777-7777-777777777777',
    lot_number: 'LOT-7',
    target_date: null,
    target_date_source: null,
    target_date_demand_item_id: null,
    ...overrides,
  })
}

async function openDialog(lot: LotSummaryResponse) {
  const wrapper = mountWithApp(LotRequiredDeliveryDateDialog, { attachTo: document.body })
  ;(wrapper.vm as unknown as LotRequiredDeliveryDateDialogVm).open(lot)
  await flushPromises()
  return wrapper
}

async function clickButton(wrapper: Awaited<ReturnType<typeof openDialog>>, index: number) {
  await wrapper.findAllComponents({ name: 'Button' }).at(index)!.trigger('click')
  await flushPromises()
}

describe('LotRequiredDeliveryDateDialog', () => {
  beforeEach(() => {
    updateMock.mockReset().mockResolvedValue(makeLot())
  })

  it('saves the picked date through the lots store and emits saved', async () => {
    const wrapper = await openDialog(makeLot({ required_delivery_date: null }))

    const picker = wrapper.findComponent({ name: 'DatePicker' })
    expect(picker.exists()).toBe(true)
    picker.vm.$emit('update:modelValue', new Date(2026, 3, 15))
    await flushPromises()

    await clickButton(wrapper, -1) // Save is the last footer button

    expect(updateMock).toHaveBeenCalledWith(7, {
      required_delivery_date: '2026-04-15',
      expected_edit_version: 0,
    })
    expect(wrapper.emitted('saved')).toHaveLength(1)

    wrapper.unmount()
  })

  it('sends null when the date is cleared', async () => {
    const wrapper = await openDialog(makeLot({ required_delivery_date: '2026-03-01' }))

    const picker = wrapper.findComponent({ name: 'DatePicker' })
    picker.vm.$emit('update:modelValue', null)
    await flushPromises()

    await clickButton(wrapper, -1)

    expect(updateMock).toHaveBeenCalledWith(7, {
      required_delivery_date: null,
      expected_edit_version: 0,
    })

    wrapper.unmount()
  })

  it('does not call update when Cancel is clicked', async () => {
    const wrapper = await openDialog(makeLot({ required_delivery_date: '2026-03-01' }))

    // Footer buttons: [0] the Dialog's own close (X), [1] Cancel, [2] Save.
    await clickButton(wrapper, 1)

    expect(updateMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeUndefined()

    wrapper.unmount()
  })
})
