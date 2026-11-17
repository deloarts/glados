import { describe, it, expect } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import {
  createCatalogueColumnsStore,
  createEmptyCatalogueFilters,
  createEmptyDateRangeFilters,
  toCatalogueFilterParams,
  toDateRangeFilterParams,
} from '../createCatalogueColumnsStore'

import type { CatalogueFilterConfig, CatalogueRawColumn } from '../createCatalogueColumnsStore'
import type { DataTableFilterMeta } from 'openvue/datatable'

type TestField = 'id' | 'name' | 'supplier_id' | 'created'
type TestFilterType = 'number' | 'text' | 'supplier' | 'date-range'

const COLUMNS: CatalogueRawColumn<TestField, TestFilterType>[] = [
  { field: 'id', headerKey: 'test.id', filter: 'number' },
  { field: 'name', headerKey: 'test.name', filter: 'text' },
  { field: 'supplier_id', headerKey: 'test.supplier', filter: 'supplier', filterParamField: 'sup' },
  { field: 'created', headerKey: 'test.created', filter: 'date-range' },
]

const CONFIG: CatalogueFilterConfig<TestFilterType> = {
  filterMatchModes: {
    number: FilterMatchMode.EQUALS,
    text: FilterMatchMode.CONTAINS,
    supplier: FilterMatchMode.EQUALS,
  },
  numericFilterTypes: new Set(['number', 'supplier']),
}

describe('createEmptyCatalogueFilters', () => {
  it('creates one entry per filterable, non-date-range column with the right match mode', () => {
    const filters = createEmptyCatalogueFilters(COLUMNS, CONFIG)

    expect(filters).toEqual({
      id: { value: null, matchMode: FilterMatchMode.EQUALS },
      name: { value: null, matchMode: FilterMatchMode.CONTAINS },
      supplier_id: { value: null, matchMode: FilterMatchMode.EQUALS },
    })
    expect(filters.created).toBeUndefined()
  })
})

describe('createEmptyDateRangeFilters', () => {
  it('creates a [null, null] entry only for date-range columns', () => {
    expect(createEmptyDateRangeFilters(COLUMNS)).toEqual({ created: [null, null] })
  })
})

describe('toCatalogueFilterParams', () => {
  it('coerces configured numeric filter types to Number and leaves others as-is', () => {
    const filters: DataTableFilterMeta = {
      id: { value: '42', matchMode: FilterMatchMode.EQUALS },
      name: { value: 'widget', matchMode: FilterMatchMode.CONTAINS },
      supplier_id: { value: '7', matchMode: FilterMatchMode.EQUALS },
    }

    expect(toCatalogueFilterParams(filters, COLUMNS, CONFIG)).toEqual({
      id: 42,
      name: 'widget',
      sup: 7, // filterParamField override
    })
  })

  it('skips null, undefined, and empty-string values', () => {
    const filters: DataTableFilterMeta = {
      id: { value: null, matchMode: FilterMatchMode.EQUALS },
      name: { value: '', matchMode: FilterMatchMode.CONTAINS },
    }

    expect(toCatalogueFilterParams(filters, COLUMNS, CONFIG)).toEqual({})
  })

  it('ignores date-range and unfiltered columns entirely', () => {
    const filters: DataTableFilterMeta = {
      created: { value: '2026-01-01', matchMode: FilterMatchMode.EQUALS },
    }

    expect(toCatalogueFilterParams(filters, COLUMNS, CONFIG)).toEqual({})
  })
})

describe('a date column that also filters by a person', () => {
  const WITH_CREATOR: CatalogueRawColumn<TestField, TestFilterType>[] = [
    { field: 'name', headerKey: 'test.name', filter: 'text' },
    { field: 'created', headerKey: 'test.created', filter: 'date-range', userFilterParam: 'creator_id' },
  ]

  it('keeps an equals entry for the person in the filter model', () => {
    expect(createEmptyCatalogueFilters(WITH_CREATOR, CONFIG)).toEqual({
      name: { value: null, matchMode: FilterMatchMode.CONTAINS },
      creator_id: { value: null, matchMode: FilterMatchMode.EQUALS },
    })
  })

  it('sends the picked person as a number and leaves an empty one out', () => {
    const picked: DataTableFilterMeta = { creator_id: { value: '3', matchMode: FilterMatchMode.EQUALS } }
    expect(toCatalogueFilterParams(picked, WITH_CREATOR, CONFIG)).toEqual({ creator_id: 3 })

    const empty: DataTableFilterMeta = { creator_id: { value: null, matchMode: FilterMatchMode.EQUALS } }
    expect(toCatalogueFilterParams(empty, WITH_CREATOR, CONFIG)).toEqual({})
  })
})

describe('toDateRangeFilterParams', () => {
  it('emits _from/_to params only for set bounds', () => {
    const params = toDateRangeFilterParams({
      created: [new Date('2026-01-01'), new Date('2026-01-31')],
    })

    expect(params).toEqual({ created_from: '2026-01-01', created_to: '2026-01-31' })
  })

  it('omits a bound left null', () => {
    const params = toDateRangeFilterParams({ created: [new Date('2026-01-01'), null] })

    expect(params).toEqual({ created_from: '2026-01-01' })
    expect(params.created_to).toBeUndefined()
  })
})

// createCatalogueColumnsStore uses useI18n() internally, which needs a real
// component instance (not just an active Pinia app) to resolve.
function mountStore() {
  const useStore = createCatalogueColumnsStore('testCatalogueColumns', {
    columns: COLUMNS,
    defaultVisibleFields: ['id', 'name'],
  })
  let store!: ReturnType<typeof useStore>

  mount(
    defineComponent({
      setup() {
        store = useStore()
        return () => h('div')
      },
    }),
    {
      global: {
        plugins: [createPinia(), createI18n({ legacy: false, locale: 'en', messages: { en: {} } })],
      },
    },
  )

  return store
}

describe('createCatalogueColumnsStore', () => {
  it('resolves column headers via i18n (missing keys fall back to the key itself)', () => {
    const store = mountStore()
    expect(store.columns.map((c) => c.header)).toEqual([
      'test.id',
      'test.name',
      'test.supplier',
      'test.created',
    ])
  })

  it('visibleColumns reflects only the default-visible fields initially', () => {
    const store = mountStore()
    expect(store.visibleColumns.map((c) => c.field)).toEqual(['id', 'name'])
  })

  it('setVisibleFields updates which columns are visible', () => {
    const store = mountStore()
    store.setVisibleFields(['supplier_id', 'created'])
    expect(store.visibleColumns.map((c) => c.field)).toEqual(['supplier_id', 'created'])
  })

  it('reset restores the default visible fields', () => {
    const store = mountStore()
    store.setVisibleFields(['created'])
    store.reset()
    expect(store.visibleFields).toEqual(['id', 'name'])
  })
})
