import { describe, it, expect, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { useFilterMetaWatch } from '../useFilterMetaWatch'

function meta(name: string | null, level: string | null): DataTableFilterMeta {
  return {
    name: { value: name, matchMode: 'contains' },
    level: { value: level, matchMode: 'equals' },
  }
}

describe('useFilterMetaWatch', () => {
  it('fires only for the watched fields, even when the whole meta object is replaced', async () => {
    const filters = ref<DataTableFilterMeta>(meta(null, null))
    const onText = vi.fn<() => void>()
    const onSelect = vi.fn<() => void>()
    useFilterMetaWatch(filters, ['name'], onText)
    useFilterMetaWatch(filters, ['level'], onSelect)

    filters.value = meta('acme', null)
    await nextTick()
    expect(onText).toHaveBeenCalledTimes(1)
    expect(onSelect).not.toHaveBeenCalled()

    filters.value = meta('acme', 'A')
    await nextTick()
    expect(onText).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it('fires when a watched value is mutated in place', async () => {
    const filters = ref<DataTableFilterMeta>(meta(null, null))
    const onChange = vi.fn<() => void>()
    useFilterMetaWatch(filters, ['name'], onChange)

    ;(filters.value.name as { value: unknown }).value = 'acme'
    await nextTick()
    expect(onChange).toHaveBeenCalledTimes(1)
  })
})
