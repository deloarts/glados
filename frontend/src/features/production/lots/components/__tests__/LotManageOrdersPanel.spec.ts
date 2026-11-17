import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotManageOrdersPanel from '../LotManageOrdersPanel.vue'

import { makeLot, makePosition } from '../../__tests__/fixtures'

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(LotManageOrdersPanel, {
    pinia,
    props: { lotId: 1 },
    global: {
      stubs: { RouterLink: true },
    },
  })
  return { wrapper, detailStore: useProductionLotDetailStore() }
}

describe('LotManageOrdersPanel', () => {
  it('renders every unassigned position on the loaded lot', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 }), makePosition({ id: 2, sequence: 2 })])
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('Milling')
  })

  it('shows the empty state when the lot has no unassigned positions', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1, kind: 'external', order_item_id: 99 })])
    await flushPromises()

    expect(wrapper.findAll('.row-card')).toHaveLength(0)
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('warns when no step on the position is flagged as typically outsourced', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })])
    await flushPromises()

    expect(wrapper.get('.row-card').find('.external-note-icon').exists()).toBe(true)
  })

  it('does not warn when a step on the position is flagged as typically outsourced', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        steps: [
          {
            id: 1,
            public_id: '11111111-1111-1111-1111-111111111111',
            created: '2026-07-01',
            note: null,
            estimated_setup_minutes: null,
            estimated_minutes_per_piece: null,
            time_budget_per_piece: null,
            sequence: 1,
            creator_id: 1,
            fabrication_method_id: 1,
            role: 'fabrication' as const,
            inspection_method_id: null,
            inspection_method_name: null,
            inspection_method_requires_evidence: null,
            fabrication_method_name: { enGB: 'Anodizing' },
            fabrication_method_requires_machine: false,
            fabrication_method_required_external: true,
            fabrication_method_default_supplier_id: 7,
            lot_id: 1,
            position_id: 1,
            source_process_id: null,
          },
        ],
      }),
    ])
    await flushPromises()

    expect(wrapper.get('.row-card').find('.external-note-icon').exists()).toBe(false)
  })

  it('does not expand a position row until an order is selected', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })])
    await flushPromises()

    await wrapper.get('.row-header').trigger('click')
    await flushPromises()

    expect(wrapper.find('.row-form').exists()).toBe(false)
  })

  it('calls assignPosition once a target and unit are chosen', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })])
    detailStore.assignPosition = vi
      .fn<typeof detailStore.assignPosition>()
      .mockResolvedValue(undefined)
    await flushPromises()

    const orderSelect = wrapper.findComponent({ name: 'OrderSelect' })
    await orderSelect.vm.$emit('update:modelValue', makeOrderResponse({ id: 9 }))
    await flushPromises()

    await wrapper.get('.row-header').trigger('click')
    await flushPromises()

    const unitSelect = wrapper.get('.row-form').findComponent({ name: 'Select' })
    await unitSelect.vm.$emit('update:modelValue', 'PCS')
    await flushPromises()

    await wrapper.get('.row-form').trigger('submit')
    await flushPromises()

    expect(detailStore.assignPosition).toHaveBeenCalledWith(
      1,
      1,
      expect.objectContaining({ order_id: 9, unit: 'PCS' }),
    )
  })

  it('pre-fills the create-order form with the expanded position’s preferred supplier', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        steps: [
          {
            id: 1,
            public_id: '11111111-1111-1111-1111-111111111111',
            created: '2026-07-01',
            note: null,
            estimated_setup_minutes: null,
            estimated_minutes_per_piece: null,
            time_budget_per_piece: null,
            sequence: 1,
            creator_id: 1,
            fabrication_method_id: 1,
            role: 'fabrication' as const,
            inspection_method_id: null,
            inspection_method_name: null,
            inspection_method_requires_evidence: null,
            fabrication_method_name: { enGB: 'Anodizing' },
            fabrication_method_requires_machine: false,
            fabrication_method_required_external: true,
            fabrication_method_default_supplier_id: 7,
            lot_id: 1,
            position_id: 1,
            source_process_id: null,
          },
        ],
      }),
    ])
    await flushPromises()

    const orderSelect = wrapper.findComponent({ name: 'OrderSelect' })
    await orderSelect.vm.$emit('update:modelValue', makeOrderResponse({ id: 9 }))
    await flushPromises()

    await wrapper.get('.row-header').trigger('click')
    await flushPromises()

    const createForm = wrapper.findComponent({ name: 'OrderCreateForm' })
    expect(createForm.props('presetSupplierId')).toBe(7)
  })
})
