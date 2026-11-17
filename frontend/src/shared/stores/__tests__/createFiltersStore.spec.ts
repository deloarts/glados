import { ref } from 'vue'
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createFiltersStore } from '../createFiltersStore'
import type { FiltersStoreBase } from '../createFiltersStore'

// Type aliases, not interfaces: createFiltersStore's TFields constraint
// requires a string index signature, which only a type alias's object type
// gets inferred implicitly; a structurally-identical interface fails it.
type TestFields = {
  search: string
  count: number
  tags: string[]
}

// Vue's ref() wraps an array/object default in a reactive Proxy, so even in
// the pristine state `field.value !== theRawDefaultArray`. The generic
// default-equality predicate is therefore only safe for scalar fields (see
// the dedicated reference-type test below). Most of this suite uses this
// scalar-only shape so it isn't accidentally exercising that caveat.
type ScalarFields = {
  search: string
  count: number
}

type TestSortField = 'name' | 'date'

describe('createFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts every field at its configured default', () => {
    const store = createFiltersStore<TestFields, never, false>('testFilters1', {
      defaults: { search: '', count: 0, tags: [] },
      sortable: false,
    })()

    expect(store.search).toBe('')
    expect(store.count).toBe(0)
    expect(store.tags).toEqual([])
  })

  it('resolves a factory default fresh on every read, so mutable defaults never leak a shared reference', () => {
    const store = createFiltersStore<TestFields, never, false>('testFilters2', {
      defaults: () => ({ search: '', count: 0, tags: [] }),
      sortable: false,
    })()

    store.tags.push('mutated')
    store.clearAll()

    expect(store.tags).toEqual([])
  })

  describe('hasActiveFilters (generic default-equality predicate)', () => {
    it('reports false in the default state', () => {
      const store = createFiltersStore<ScalarFields, never, false>('testFilters3', {
        defaults: { search: '', count: 0 },
        sortable: false,
      })()
      expect(store.hasActiveFilters).toBe(false)
    })

    it('reports true once a scalar field differs from its default', () => {
      const store = createFiltersStore<ScalarFields, never, false>('testFilters4', {
        defaults: { search: '', count: 0 },
        sortable: false,
      })()
      store.search = 'abc'
      expect(store.hasActiveFilters).toBe(true)
    })

    it('reverts to false once the field is put back to its default', () => {
      const store = createFiltersStore<ScalarFields, never, false>('testFilters5', {
        defaults: { search: '', count: 0 },
        sortable: false,
      })()
      store.count = 3
      expect(store.hasActiveFilters).toBe(true)
      store.count = 0
      expect(store.hasActiveFilters).toBe(false)
    })

    // The generic predicate compares by reference, so an array/object field
    // reset to a *new* empty value (as clearAll does) never again equals
    // its original default object. This is exactly why the factory takes
    // a custom `isActive` for fields like this instead of forcing everyone
    // through the generic diff. Documented here so nobody "fixes" it later.
    it('treats a reference-type field as permanently active once ever touched, by design - callers must pass isActive for these', () => {
      const store = createFiltersStore<TestFields, never, false>('testFilters6', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
      })()
      store.tags = ['x']
      store.clearAll()
      expect(store.tags).toEqual([])
      expect(store.hasActiveFilters).toBe(true)
    })
  })

  describe('custom isActive', () => {
    it('is used instead of the generic predicate when provided', () => {
      const store = createFiltersStore<TestFields, never, false>('testFilters7', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
        isActive: (fields) => fields.tags.length > 0,
      })()

      store.search = 'ignored by the custom predicate'
      expect(store.hasActiveFilters).toBe(false)

      store.tags = ['x']
      expect(store.hasActiveFilters).toBe(true)

      store.clearAll()
      expect(store.hasActiveFilters).toBe(false)
    })
  })

  describe('clearAll', () => {
    it('resets every field to its default and bumps clearTrigger', () => {
      const store = createFiltersStore<TestFields, never, false>('testFilters8', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
      })()
      store.search = 'abc'
      store.count = 5
      store.tags = ['x', 'y']
      const before = store.clearTrigger

      store.clearAll()

      expect(store.search).toBe('')
      expect(store.count).toBe(0)
      expect(store.tags).toEqual([])
      expect(store.clearTrigger).toBe(before + 1)
    })

    it('bumps clearTrigger even when every field was already at its default', () => {
      const store = createFiltersStore<TestFields, never, false>('testFilters9', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
      })()
      const before = store.clearTrigger
      store.clearAll()
      expect(store.clearTrigger).toBe(before + 1)
    })
  })

  describe('sortable', () => {
    it('omits sort state entirely when sortable is not set', () => {
      const store = createFiltersStore<TestFields, never, false>('testFilters10', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
      })()
      expect((store as { sortBy?: unknown }).sortBy).toBeUndefined()
      expect((store as { setSort?: unknown }).setSort).toBeUndefined()
    })

    it('starts at sortBy null, sortDir asc', () => {
      const store = createFiltersStore<TestFields, TestSortField, true>('testFilters11', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: true,
      })()
      expect(store.sortBy).toBeNull()
      expect(store.sortDir).toBe('asc')
    })

    it('setSort sets both field and direction', () => {
      const store = createFiltersStore<TestFields, TestSortField, true>('testFilters12', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: true,
      })()
      store.setSort('name', 'desc')
      expect(store.sortBy).toBe('name')
      expect(store.sortDir).toBe('desc')
    })

    it('clearSort resets to sortBy null, sortDir asc', () => {
      const store = createFiltersStore<TestFields, TestSortField, true>('testFilters13', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: true,
      })()
      store.setSort('date', 'desc')
      store.clearSort()
      expect(store.sortBy).toBeNull()
      expect(store.sortDir).toBe('asc')
    })

    it('clearAll also clears the sort', () => {
      const store = createFiltersStore<TestFields, TestSortField, true>('testFilters14', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: true,
      })()
      store.setSort('name', 'desc')
      store.clearAll()
      expect(store.sortBy).toBeNull()
      expect(store.sortDir).toBe('asc')
    })
  })

  describe('extend', () => {
    function extendWithFlag() {
      return { state: { extraFlag: false } }
    }

    it('merges extra state/actions onto the store', () => {
      const store = createFiltersStore<
        TestFields,
        never,
        false,
        ReturnType<typeof extendWithFlag>['state']
      >('testFilters15', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
        extend: extendWithFlag,
      })()
      expect(store.extraFlag).toBe(false)
    })

    function extendWithBaseAccess(base: FiltersStoreBase<TestFields, never, false>) {
      return {
        state: {
          armFromExtra: () => {
            base.count.value = 42
          },
        },
      }
    }

    it('gives extend access to the generic base to read/write it', () => {
      const store = createFiltersStore<
        TestFields,
        never,
        false,
        ReturnType<typeof extendWithBaseAccess>['state']
      >('testFilters16', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
        extend: extendWithBaseAccess,
      })()
      store.armFromExtra()
      expect(store.count).toBe(42)
    })

    it('runs onClear as part of clearAll, after the generic fields reset and before clearTrigger bumps', () => {
      const calls: string[] = []
      function extendWithOnClear() {
        return { state: {}, onClear: () => calls.push('onClear') }
      }
      const store = createFiltersStore<
        TestFields,
        never,
        false,
        ReturnType<typeof extendWithOnClear>['state']
      >('testFilters17', {
        defaults: { search: '', count: 0, tags: [] },
        sortable: false,
        extend: extendWithOnClear,
      })()
      store.search = 'abc'
      const before = store.clearTrigger

      store.clearAll()

      expect(calls).toEqual(['onClear'])
      expect(store.clearTrigger).toBe(before + 1)
    })

    function extendWithGroupBy() {
      const groupBy = ref<string | null>(null)
      return {
        state: {
          groupBy,
          setGroupBy: (value: string) => {
            groupBy.value = value
          },
        },
        onClear: () => {
          groupBy.value = null
        },
      }
    }

    it("resets an extend-local field via onClear even though it isn't part of hasActiveFilters", () => {
      const store = createFiltersStore<
        ScalarFields,
        never,
        false,
        ReturnType<typeof extendWithGroupBy>['state']
      >('testFilters18', {
        defaults: { search: '', count: 0 },
        sortable: false,
        extend: extendWithGroupBy,
      })()

      store.setGroupBy('status')
      expect(store.groupBy).toBe('status')
      expect(store.hasActiveFilters).toBe(false)

      store.clearAll()
      expect(store.groupBy).toBeNull()
    })
  })
})
