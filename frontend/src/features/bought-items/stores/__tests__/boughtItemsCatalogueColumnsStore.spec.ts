import { describe, it, expect } from 'vitest'

import {
  createEmptyBoughtItemFilters,
  createEmptyDateRangeFilters,
  toBoughtItemFilterParams,
  toDateRangeFilterParams,
  BOUGHT_ITEM_STATUS_OPTIONS,
} from '../boughtItemsCatalogueColumnsStore'
import type { DataTableFilterMeta } from 'openvue/datatable'

// The generic filter-model plumbing (createEmptyCatalogueFilters,
// toCatalogueFilterParams, ...) lives in and is covered by
// createCatalogueColumnsStore.spec.ts. This spec covers what's genuinely
// bought-items-specific: the column list and FILTER_CONFIG (which columns
// are filterable, which type, which need filterParamField redirection and
// numeric coercion for the actual backend API contract).
describe('boughtItemsCatalogueColumnsStore filter mapping', () => {
  it('BOUGHT_ITEM_STATUS_OPTIONS lists the three catalogue statuses', () => {
    expect(BOUGHT_ITEM_STATUS_OPTIONS).toEqual(['active', 'inactive', 'replaced'])
  })

  it('creates an empty filter meta entry only for filterable columns, skipping display-only ones', () => {
    const filters = createEmptyBoughtItemFilters()

    expect(filters.article_name).toEqual({ value: null, matchMode: 'contains' })
    expect(filters.id).toEqual({ value: null, matchMode: 'equals' })
    // 'pdf_files' has no `filter` set: display-only, no backend query param.
    expect(filters.pdf_files).toBeUndefined()
    // 'created'/'changed' are date-range, tracked separately.
    expect(filters.created).toBeUndefined()
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

    expect(toBoughtItemFilterParams(filters)).toEqual({ article_name: 'widget' })
  })

  it('redirects the manufacturer (supplier) column to manufacturer_id and coerces it to a number', () => {
    const filters: DataTableFilterMeta = {
      manufacturer_name: { value: '42', matchMode: 'equals' },
    }

    expect(toBoughtItemFilterParams(filters)).toEqual({ manufacturer_id: 42 })
  })

  it('redirects the article_groups column to article_group_id and coerces it to a number', () => {
    const filters: DataTableFilterMeta = {
      article_groups: { value: 7, matchMode: 'equals' },
    }

    expect(toBoughtItemFilterParams(filters)).toEqual({ article_group_id: 7 })
  })

  it('sends the creator picked in the created column as creator_id', () => {
    const filters: DataTableFilterMeta = {
      creator_id: { value: 3, matchMode: 'equals' },
    }

    expect(toBoughtItemFilterParams(filters)).toEqual({ creator_id: 3 })
  })

  it('coerces a plain number column (mass) to a number', () => {
    const filters: DataTableFilterMeta = {
      mass: { value: '1.5', matchMode: 'equals' },
    }

    expect(toBoughtItemFilterParams(filters)).toEqual({ mass: 1.5 })
  })

  it('omits empty/null filter values entirely rather than sending blank params', () => {
    const filters: DataTableFilterMeta = {
      article_name: { value: '', matchMode: 'contains' },
      part_number: { value: null, matchMode: 'contains' },
    }

    expect(toBoughtItemFilterParams(filters)).toEqual({})
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
