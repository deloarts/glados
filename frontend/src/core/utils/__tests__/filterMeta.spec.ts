import { describe, it, expect } from 'vitest'
import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { filterMetaValue, hasActiveFilterMeta } from '../filterMeta'

function meta(value: unknown) {
  return { value, matchMode: FilterMatchMode.EQUALS }
}

describe('filterMetaValue', () => {
  it('returns the value of a plain filter meta', () => {
    const filters: DataTableFilterMeta = { name: meta('abc'), active: meta(false) }
    expect(filterMetaValue(filters, 'name')).toBe('abc')
    expect(filterMetaValue(filters, 'active')).toBe(false)
  })

  it('returns null for a missing field or an operator meta', () => {
    const filters: DataTableFilterMeta = {
      grouped: { operator: 'and', constraints: [meta('x')] },
    }
    expect(filterMetaValue(filters, 'missing')).toBeNull()
    expect(filterMetaValue(filters, 'grouped')).toBeNull()
  })
})

describe('hasActiveFilterMeta', () => {
  it('is false while every value is empty', () => {
    expect(hasActiveFilterMeta({ a: meta(null), b: meta(undefined), c: meta('') })).toBe(false)
    expect(hasActiveFilterMeta({})).toBe(false)
  })

  it('counts false and 0 as active values', () => {
    expect(hasActiveFilterMeta({ a: meta(false) })).toBe(true)
    expect(hasActiveFilterMeta({ a: meta(0) })).toBe(true)
    expect(hasActiveFilterMeta({ a: meta('x') })).toBe(true)
  })

  it('counts a range or multi-select only with a picked entry', () => {
    expect(hasActiveFilterMeta({ a: meta([]) })).toBe(false)
    expect(hasActiveFilterMeta({ a: meta([null, null]) })).toBe(false)
    expect(hasActiveFilterMeta({ a: meta([null, 5]) })).toBe(true)
  })

  it('ignores operator metas', () => {
    expect(
      hasActiveFilterMeta({ a: { operator: 'and', constraints: [meta('x')] } }),
    ).toBe(false)
  })
})
