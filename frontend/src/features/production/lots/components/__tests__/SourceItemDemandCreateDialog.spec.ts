import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

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

// Mounts closed and then opens, the way every call site does: the form reset
// (and the picker-mode latch) hangs off the visible false -> true transition.
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

function lotsCalls(): Array<{ params?: Record<string, unknown> }> {
  return getMock.mock.calls
    .filter(([url]) => url === '/production-lots/')
    .map(([, config]) => config ?? {})
}

describe('SourceItemDemandCreateDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 50, skip: 0 } })
    postMock.mockResolvedValue({ data: { id: 1 } })
  })

  it('pinned to a lot: no picker, quantity seeded from the lot, posts that lot id', async () => {
    const wrapper = await openDialog({ lotId: 7, lotQuantity: 12 })

    expect(wrapper.findComponent(LotSelect).exists()).toBe(false)
    expect(lotsCalls()).toHaveLength(0)

    await clickSave(wrapper)

    expect(postMock).toHaveBeenCalledWith(
      '/source-item-demands',
      expect.objectContaining({ lot_id: 7, quantity: 12, unit: 'PCS' }),
    )

    wrapper.unmount()
  })

  it('picker mode: fetches demandable lots and drops the ones the backend would reject', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [
          makeLot({ id: 1, lot_number: 'LOT-1' }),
          // Already has a demand linked; create_source_item_demand rejects it.
          makeLot({ id: 2, lot_number: 'LOT-2', input_demand_id: 42 }),
          // No material source at all; likewise rejected.
          makeLot({ id: 3, lot_number: 'LOT-3', source_item_id: null }),
        ],
        total: 3,
        limit: 50,
        skip: 0,
      },
    })

    const wrapper = await openDialog()

    const select = wrapper.findComponent(LotSelect)
    expect(select.exists()).toBe(true)
    expect(lotsCalls()[0]?.params).toMatchObject({ actionable_for: 'source' })

    const options = select
      .findComponent({ name: 'Select' })
      .props('options') as LotSummaryResponse[]
    expect(options.map((lot) => lot.id)).toEqual([1])

    wrapper.unmount()
  })

  it('picker mode: selecting a lot prefills the quantity and drives the posted lot id', async () => {
    const wrapper = await openDialog()

    wrapper.findComponent(LotSelect).vm.$emit('update:modelValue', makeLot({ id: 9, quantity: 25 }))
    await flushPromises()

    await clickSave(wrapper)

    expect(postMock).toHaveBeenCalledWith(
      '/source-item-demands',
      expect.objectContaining({ lot_id: 9, quantity: 25, unit: 'PCS' }),
    )

    wrapper.unmount()
  })

  it('picker mode: refuses to submit without a lot', async () => {
    const wrapper = await openDialog()

    await clickSave(wrapper)

    expect(postMock).not.toHaveBeenCalled()
    // The dialog teleports to body, so assert against the document, not the wrapper.
    expect(document.body.textContent).toContain(
      i18n.global.t('sourceItems.demands.create.errors.required') as string,
    )

    wrapper.unmount()
  })

  it('associates every field label with its control via id/for (pinned mode)', async () => {
    const wrapper = await openDialog({ lotId: 7, lotQuantity: 12 })

    const labels = document.querySelectorAll('.form-grid label')
    // quantity, unit, itemsPerUnit, desiredDeliveryDate, high_priority, notify_on_delivery, note
    expect(labels.length).toBe(7)

    labels.forEach((label) => {
      const forId = label.getAttribute('for')
      expect(forId).toBeTruthy()
      expect(document.getElementById(forId!)).not.toBeNull()
    })

    wrapper.unmount()
  })

  it('marks required fields with aria-required, leaving optional fields unmarked', async () => {
    const wrapper = await openDialog({ lotId: 7, lotQuantity: 12 })

    const quantityInput = wrapper.findComponent({ name: 'InputNumber' }).find('[role="spinbutton"]')
    expect(quantityInput.attributes('aria-required')).toBe('true')

    const unitCombobox = wrapper.findComponent({ name: 'Select' }).find('[role="combobox"]')
    expect(unitCombobox.attributes('aria-required')).toBe('true')

    const itemsPerUnitInput = wrapper
      .findAllComponents({ name: 'InputNumber' })
      .at(1)!
      .find('[role="spinbutton"]')
    expect(itemsPerUnitInput.attributes('aria-required')).toBeUndefined()

    const noteTextarea = wrapper.findComponent({ name: 'Textarea' })
    expect(noteTextarea.attributes('aria-required')).toBeUndefined()

    wrapper.unmount()
  })

  it('picker mode: marks the lot field as required with an associated label and aria-required', async () => {
    const wrapper = await openDialog()

    const lotLabel = Array.from(document.querySelectorAll('.form-grid label')).find((label) =>
      label.textContent?.includes(i18n.global.t('sourceItems.demands.create.fields.lot') as string),
    )!
    expect(lotLabel.querySelector('span[aria-hidden="true"]')?.textContent).toBe(' *')

    const lotCombobox = wrapper.findComponent(LotSelect).find('[role="combobox"]')
    expect(lotCombobox.attributes('id')).toBe(lotLabel.getAttribute('for'))
    expect(lotCombobox.attributes('aria-required')).toBe('true')

    wrapper.unmount()
  })
})
