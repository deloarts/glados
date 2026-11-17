import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { useFilterMetaModel, useKeyedFilterMetaModel } from '../useFilterMetaModel'

describe('useFilterMetaModel', () => {
  it('reads the value of one field, null when it is unset', () => {
    const filters = ref<DataTableFilterMeta>({ creator_id: { value: 3, matchMode: 'equals' } })
    expect(useFilterMetaModel<number>(filters, 'creator_id').value).toBe(3)
    expect(useFilterMetaModel<number>(filters, 'missing').value).toBeNull()
  })

  it('writes a new meta object and keeps the match mode', () => {
    const original: DataTableFilterMeta = {
      creator_id: { value: null, matchMode: 'equals' },
      name: { value: 'abc', matchMode: 'contains' },
    }
    const filters = ref<DataTableFilterMeta>(original)
    const model = useFilterMetaModel<number>(filters, 'creator_id')

    model.value = 4

    expect(filters.value).not.toBe(original)
    expect(filters.value).toEqual({
      creator_id: { value: 4, matchMode: 'equals' },
      name: { value: 'abc', matchMode: 'contains' },
    })

    model.value = undefined
    expect(filterValue(filters.value)).toBeNull()
  })
})

describe('useKeyedFilterMetaModel', () => {
  it('reads and writes the named field, then reports the change', () => {
    const filters = ref<DataTableFilterMeta>({})
    const onChange = vi.fn<() => void>()
    const { getFilterValue, setFilterValue } = useKeyedFilterMetaModel(filters, onChange)

    expect(getFilterValue<number>('creator_id')).toBeNull()
    setFilterValue('creator_id', 7)

    expect(getFilterValue<number>('creator_id')).toBe(7)
    expect(filters.value).toEqual({ creator_id: { value: 7, matchMode: 'equals' } })
    expect(onChange).toHaveBeenCalledTimes(1)
  })
})

function filterValue(filters: DataTableFilterMeta): unknown {
  const meta = filters.creator_id
  return typeof meta === 'object' && 'value' in meta ? meta.value : 'unset'
}
