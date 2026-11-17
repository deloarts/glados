import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import InputNumber from 'openvue/inputnumber'
import DatePicker from 'openvue/datepicker'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemDemandResponse } from '@/test-utils/factories'
import { useMadeItemsProcurementStore } from '../../stores/madeItemsProcurementStore'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MadeItemsDemandsManageLots from '../MadeItemsDemandsManageLots.vue'
import { useMadeItemsDemandsStore } from '@/features/made-items'

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(MadeItemsDemandsManageLots, {
    pinia,
    global: {
      stubs: { RouterLink: true },
    },
  })
  return {
    wrapper,
    procurementStore: useMadeItemsProcurementStore(),
    demandsStore: useMadeItemsDemandsStore(),
  }
}

describe('MadeItemsDemandsManageLots', () => {
  it('groups demands for the same made item and project into one row', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeMadeItemDemandResponse({ id: 1, quantity: 5 }),
      makeMadeItemDemandResponse({ id: 2, quantity: 3 }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(1)
    expect(rows[0]!.text()).toContain('Bracket')
    expect(rows[0]!.findAll('.demand-row')).toHaveLength(2)
  })

  it('keeps demands from different projects in separate rows', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeMadeItemDemandResponse({ id: 1, quantity: 5, project_id: 1, project_number: 'P-001' }),
      makeMadeItemDemandResponse({ id: 2, quantity: 3, project_id: 2, project_number: 'P-002' }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
  })

  it('keeps demands for different made items in separate rows', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeMadeItemDemandResponse({ id: 1, quantity: 5, made_item_id: 1 }),
      makeMadeItemDemandResponse({ id: 2, quantity: 3, made_item_id: 2 }),
    ]
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
  })

  it('flags a row with the zero-quantity warning when fully allocated', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeMadeItemDemandResponse({ id: 1, quantity: 0 })]
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.classes()).toContain('row-card--zero-qty')
    expect(row.find('.zero-qty-badge').exists()).toBe(true)
  })

  it('does not flag a row that still has quantity to allocate', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeMadeItemDemandResponse({ id: 1, quantity: 5 })]
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.classes()).not.toContain('row-card--zero-qty')
    expect(row.find('.zero-qty-badge').exists()).toBe(false)
  })

  it('walks the demand allocation down when the lot quantity is lowered', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeMadeItemDemandResponse({ id: 1, quantity: 14 })]
    await flushPromises()

    const lotQuantity = wrapper.get('.row-controls').findComponent(InputNumber)
    const demandQuantity = () => wrapper.get('.demand-row').findComponent(InputNumber)
    expect(demandQuantity().props('modelValue')).toBe(14)

    lotQuantity.vm.$emit('update:modelValue', 10)
    await flushPromises()
    expect(demandQuantity().props('modelValue')).toBe(10)

    lotQuantity.vm.$emit('update:modelValue', 14)
    await flushPromises()
    expect(demandQuantity().props('modelValue')).toBe(14)
  })

  it('fills contributing demands in order when the lot quantity is lowered', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeMadeItemDemandResponse({ id: 1, quantity: 6 }),
      makeMadeItemDemandResponse({ id: 2, quantity: 6 }),
    ]
    await flushPromises()

    wrapper.get('.row-controls').findComponent(InputNumber).vm.$emit('update:modelValue', 10)
    await flushPromises()

    const demandQuantities = wrapper
      .findAll('.demand-row')
      .map((row) => row.findComponent(InputNumber).props('modelValue'))
    expect(demandQuantities).toEqual([6, 4])
  })

  it('grows the lot quantity when a demand is allocated more than the lot produces', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeMadeItemDemandResponse({ id: 1, quantity: 6 }),
      makeMadeItemDemandResponse({ id: 2, quantity: 6 }),
    ]
    await flushPromises()

    const lotQuantity = wrapper.get('.row-controls').findComponent(InputNumber)
    lotQuantity.vm.$emit('update:modelValue', 10)
    await flushPromises()

    wrapper.findAll('.demand-row')[1]!.findComponent(InputNumber).vm.$emit('update:modelValue', 6)
    await flushPromises()

    expect(wrapper.get('.row-controls').findComponent(InputNumber).props('modelValue')).toBe(12)
  })

  it('prefills the row date from the selected demand', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [
      makeMadeItemDemandResponse({ id: 1, quantity: 5, desired_delivery_date: '2026-08-28' }),
    ]
    await flushPromises()

    const datePicker = wrapper.get('.row-controls').findComponent(DatePicker)
    expect(datePicker.props('modelValue')).toEqual(new Date(2026, 7, 28))
  })

  it('prefers the live demands-store date over a stale selected-demand snapshot', async () => {
    // Regression: a demand can be selected before its delivery date changes
    // elsewhere (e.g. propagated from a project-level date change). The
    // row must reflect the demand's current date, not the one captured at
    // selection time.
    const { wrapper, procurementStore, demandsStore } = mountPanel()
    const stale = makeMadeItemDemandResponse({ id: 1, quantity: 5, desired_delivery_date: null })
    procurementStore.selectedDemands = [stale]
    demandsStore.items = [
      makeMadeItemDemandResponse({ id: 1, quantity: 5, desired_delivery_date: '2026-08-28' }),
    ]
    await flushPromises()

    const datePicker = wrapper.get('.row-controls').findComponent(DatePicker)
    expect(datePicker.props('modelValue')).toEqual(new Date(2026, 7, 28))
  })

  it('removing the only demand in a row deselects it and removes the row', async () => {
    const { wrapper, procurementStore } = mountPanel()
    procurementStore.selectedDemands = [makeMadeItemDemandResponse({ id: 1, quantity: 5 })]
    await flushPromises()

    await wrapper.get('.demand-row button').trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(0)
    expect(wrapper.findAll('.row-card')).toHaveLength(0)
  })
})
