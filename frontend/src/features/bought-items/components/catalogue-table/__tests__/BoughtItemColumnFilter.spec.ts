import { describe, it, expect, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import BoughtItemColumnFilter from '../BoughtItemColumnFilter.vue'
import type { BoughtItemColumnDefinition } from '../../../stores/boughtItemsCatalogueColumnsStore'

// BoughtItemsCatalogueTable.vue's per-column filter dispatch. The filter
// value travels through a plain modelValue/update:modelValue pair rather than
// a direct `v-model="filterModel.value"`, which would mutate a prop. This
// covers that the value round-trips and filterCallback fires at the right
// points.

function makeColumn(overrides: Partial<BoughtItemColumnDefinition> = {}): BoughtItemColumnDefinition {
  return {
    field: 'status',
    headerKey: 'boughtItems.catalogue.columns.status',
    header: 'Status',
    filter: 'status',
    ...overrides,
  } as BoughtItemColumnDefinition
}

describe('BoughtItemColumnFilter', () => {
  it('status filter: emits the picked value and calls filterCallback on change', async () => {
    setActivePinia(createPinia())
    const filterCallback = vi.fn<() => void>()
    const wrapper = mountWithApp(BoughtItemColumnFilter, {
      props: {
        column: makeColumn({ filter: 'status' }),
        modelValue: null,
        filterCallback,
        getDateRangeModel: () => null,
        setDateRangeModel: vi.fn<(field: string, value: unknown) => void>(),
      },
    })

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.exists()).toBe(true)

    await select.vm.$emit('update:modelValue', 'active')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['active'])

    await select.vm.$emit('change')
    expect(filterCallback).toHaveBeenCalledTimes(1)
  })

  it('data-source filter: offers the labels and filters by the stored value', () => {
    setActivePinia(createPinia())
    const wrapper = mountWithApp(BoughtItemColumnFilter, {
      props: {
        column: makeColumn({ field: 'data_source', filter: 'data-source' }),
        modelValue: null,
        filterCallback: vi.fn<() => void>(),
        getDateRangeModel: () => null,
        setDateRangeModel: vi.fn<(field: string, value: unknown) => void>(),
      },
    })

    const options = wrapper.findComponent({ name: 'Select' }).props('options') as {
      label: string
      value: string | null
    }[]
    expect(options.slice(1)).toEqual([
      { label: 'Web', value: 'WEB' },
      { label: 'PDM', value: 'CAD' },
    ])
  })

  it('date-range filter: reads through getDateRangeModel and writes through setDateRangeModel', async () => {
    setActivePinia(createPinia())
    const setDateRangeModel = vi.fn<(field: string, value: unknown) => void>()
    const range: [Date, Date | null] = [new Date('2026-01-01'), null]
    const wrapper = mountWithApp(BoughtItemColumnFilter, {
      props: {
        column: makeColumn({ field: 'created', filter: 'date-range' }),
        modelValue: null,
        filterCallback: vi.fn<() => void>(),
        getDateRangeModel: () => range,
        setDateRangeModel,
      },
    })

    const datePicker = wrapper.findComponent({ name: 'DatePicker' })
    expect(datePicker.exists()).toBe(true)
    expect(datePicker.props('modelValue')).toEqual(range)

    await datePicker.vm.$emit('update:modelValue', [new Date('2026-02-01'), null])
    expect(setDateRangeModel).toHaveBeenCalledWith('created', [new Date('2026-02-01'), null])
  })

  it('text filter: emits on input and calls filterCallback', async () => {
    setActivePinia(createPinia())
    const filterCallback = vi.fn<() => void>()
    const wrapper = mountWithApp(BoughtItemColumnFilter, {
      props: {
        column: makeColumn({ field: 'article_name', header: 'Article', filter: 'text' }),
        modelValue: '',
        filterCallback,
        getDateRangeModel: () => null,
        setDateRangeModel: vi.fn<(field: string, value: unknown) => void>(),
      },
    })

    const input = wrapper.findComponent({ name: 'InputText' })
    expect(input.exists()).toBe(true)

    await input.vm.$emit('update:modelValue', 'wid')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['wid'])

    await input.vm.$emit('input')
    expect(filterCallback).toHaveBeenCalledTimes(1)
  })
})
