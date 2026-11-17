import { describe, it, expect } from 'vitest'

import {
  createEmptyMadeItemFilters,
  createEmptyDateRangeFilters,
  toMadeItemFilterParams,
  toDateRangeFilterParams,
  MADE_ITEM_STATUS_OPTIONS,
} from '../madeItemsCatalogueColumnsStore'
import type { DataTableFilterMeta } from 'openvue/datatable'

// The generic filter-model plumbing (createEmptyCatalogueFilters,
// toCatalogueFilterParams, ...) lives in and is covered by
// createCatalogueColumnsStore.spec.ts. This spec covers what's genuinely
// made-items-specific: the column list and FILTER_CONFIG (which columns
// are filterable, which type, which need filterParamField redirection and
// numeric coercion for the actual backend API contract).
describe('madeItemsCatalogueColumnsStore filter mapping', () => {
  it('MADE_ITEM_STATUS_OPTIONS lists the three catalogue statuses', () => {
    expect(MADE_ITEM_STATUS_OPTIONS).toEqual(['active', 'inactive', 'replaced'])
  })

  it('creates an empty filter meta entry only for filterable columns, skipping display-only ones', () => {
    const filters = createEmptyMadeItemFilters()

    expect(filters.article_name).toEqual({ value: null, matchMode: 'contains' })
    expect(filters.id).toEqual({ value: null, matchMode: 'equals' })
    expect(filters.status).toEqual({ value: null, matchMode: 'equals' })
    // 'image'/'files'/'processes' are synthetic/display-only columns with no `filter`.
    expect(filters.image).toBeUndefined()
    expect(filters.files).toBeUndefined()
    expect(filters.processes).toBeUndefined()
    // 'created'/'changed' are date-range, tracked separately.
    expect(filters.created).toBeUndefined()
    expect(filters.changed).toBeUndefined()
  })

  it('creates an empty date-range entry for created/changed only', () => {
    const dateRangeFilters = createEmptyDateRangeFilters()

    expect(dateRangeFilters).toEqual({
      created: [null, null],
      changed: [null, null],
    })
  })

  it('maps a text column filter straight through by field name', () => {
    const filters: DataTableFilterMeta = {
      article_name: { value: 'widget', matchMode: 'contains' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({ article_name: 'widget' })
  })

  it('sends the creator picked in the created column as creator_id', () => {
    const filters: DataTableFilterMeta = {
      creator_id: { value: 3, matchMode: 'equals' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({ creator_id: 3 })
  })

  it('redirects the article_groups column to article_group_id and coerces it to a number', () => {
    const filters: DataTableFilterMeta = {
      article_groups: { value: '7', matchMode: 'equals' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({ article_group_id: 7 })
  })

  it('coerces a plain number column (mass) to a number', () => {
    const filters: DataTableFilterMeta = {
      mass: { value: '1.5', matchMode: 'equals' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({ mass: 1.5 })
  })

  it('sends a status filter as-is, without numeric coercion', () => {
    const filters: DataTableFilterMeta = {
      status: { value: 'active', matchMode: 'equals' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({ status: 'active' })
  })

  it('sends the stored data source the label filter picked', () => {
    const filters: DataTableFilterMeta = {
      data_source: { value: 'CAD', matchMode: 'equals' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({ data_source: 'CAD' })
  })

  it('omits empty/null filter values entirely rather than sending blank params', () => {
    const filters: DataTableFilterMeta = {
      article_name: { value: '', matchMode: 'contains' },
      part_number: { value: null, matchMode: 'contains' },
    }

    expect(toMadeItemFilterParams(filters)).toEqual({})
  })

  it('maps date-range filters to {field}_from/{field}_to params', () => {
    const result = toDateRangeFilterParams({
      created: [new Date('2026-01-01'), new Date('2026-01-31')],
      changed: [null, null],
    })

    expect(result).toEqual({
      created_from: '2026-01-01',
      created_to: '2026-01-31',
    })
  })
})
