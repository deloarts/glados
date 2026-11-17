import { beforeEach, describe, expect, it } from 'vitest'
import { FilterMatchMode } from '@openvue/core/api'
import { createPinia, setActivePinia } from 'pinia'

import { createDocumentTableStores, documentTableFilter } from '../createDocumentTableStores'

const useStores = createDocumentTableStores<'kind', 'title'>('docTest', () => ({
  title: { value: null, matchMode: FilterMatchMode.CONTAINS },
}))

describe('createDocumentTableStores', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('names the stores after the prefix and the context', () => {
    const page = useStores('page')
    const project = useStores('project')

    expect(page.view.$id).toBe('docTestView-page')
    expect(page.filters.$id).toBe('docTestFilters-page')
    expect(project.filters.$id).toBe('docTestFilters-project')
  })

  it('keeps the contexts apart and bumps the refresh trigger', () => {
    const page = useStores('page')
    const product = useStores('product')

    page.filters.triggerRefresh()

    expect(page.filters.refreshTrigger).toBe(1)
    expect(product.filters.refreshTrigger).toBe(0)
  })
})

describe('documentTableFilter', () => {
  it('returns null for an unset or empty filter and the value otherwise', () => {
    const filters = {
      empty: { value: '', matchMode: FilterMatchMode.CONTAINS },
      set: { value: 'x', matchMode: FilterMatchMode.CONTAINS },
    }

    expect(documentTableFilter(filters, 'missing')).toBeNull()
    expect(documentTableFilter(filters, 'empty')).toBeNull()
    expect(documentTableFilter(filters, 'set')).toBe('x')
  })
})
